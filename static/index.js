/* Javascript needed */

Validator = function() {
	this.time = function(input) {
		i = parseInt(input);
		if (i > 23)
			i = 23;
		if (i < 1 || isNaN(i))
			i = 0;
		return i.toString();
	}

	this.delay = function(input) {
		i = parseInt(input);
		if (i < 30 || isNaN(i))
			i = 30;
		return i.toString();
	}

	this.refresh = function(input) {
		i = parseInt(input);
		if (i < 1 || isNaN(i))
			i = 1;
		return i.toString();
	}


	this.depth = function(input) {
		i = parseInt(input);
		if (isNaN(i) || [8, 16, 24, 32].indexOf(i) == -1)
			i = 8;
		return i.toString();
	}

	this.width = function(input) {
		i = parseInt(input);
		if (i < 640 || isNaN(i))
			i = 640;
		return i.toString();
	}

	this.height = function(input) {
		i = parseInt(input);
		if (i < 480 || isNaN(i))
			i = 480;
		return i.toString();
	}
}

function populateKeywords() {
	$.ajax({
		url:"/keywords",
		type:"GET",
		contentType: "application/json; charset=utf-8",
		dataType: "json"
	}).done(function(data){
		$("#keywords").empty();
		for (entry in data['keywords']) {
			$('#keywords').append('<input class="delete" type="button" data-id="' + entry + '" value="Delete"><input class="search" data-key="' + encodeURIComponent(data["keywords"][entry]) + '" type="button" value="Open"> ');
			if (data["keywords"][entry] == "")
				$('#keywords').append("&lt;empty - picks one of the last photos added&gt;");
			else
				$('#keywords').append(data["keywords"][entry]);
			$('#keywords').append('<br>');
		}
		$("input[class='search']").click(function(){
			window.open("https://photos.google.com/search/" + $(this).data('key'), "_blank");
		});
		$("input[class='delete']").click(function(){
			if (confirm("Are you sure?")) {
				$.ajax({
					url:"/keywords/delete",
					type:"POST",
					data: JSON.stringify({ id: $(this).data('id') }),
					contentType: "application/json; charset=utf-8",
					dataType: "json"
				}).done(function(data){
					populateKeywords();
				});
			}
		});
	});

	$('#test').click(function(){
		var key = $('#keyword').val().trim()
		if (key != "")
			window.open("https://photos.google.com/search/" + encodeURIComponent(key), "_blank");
		else
			window.open("https://photos.google.com/", "_blank");
	});

	$('#add').click(function(){
		$.ajax({
			url:"/keywords/add",
			type:"POST",
			data: JSON.stringify({ keywords: $('#keyword').val() }),
			contentType: "application/json; charset=utf-8",
			dataType: "json"
		}).done(function(data){
			if (data['status']) {
				populateKeywords();
				$('#keyword').val("");
			}
		});
	});
}

function loadSettings()
{
	validator = new Validator();

	var fieldmap = {
		'display-off' : {'caption' : 'Turn off display at (24 hour)', 'validate' : validator.time},
		'display-on'  : {'caption' : 'Turn on display at (24 hour)', 'validate' : validator.time},
		'interval'    : {'caption' : 'Seconds to show each image', 'validate' : validator.delay},
		'refresh-content' : {'caption' : 'Hours before reloading server image list', 'validate' : validator.refresh},
		'depth' : {'caption':'Color depth in bits (8, 16, 24 or 32)', 'validate' : validator.depth},
		'height' : { 'caption' : 'Height of display', 'validate' : validator.height},
		'width' : { 'caption' : 'Width of display', 'validate' : validator.width},
		'tvservice' : { 'caption' : 'Arguments for Raspberry Pi 3 tv service (<a href="/details/tvservice" target="_blank">show available modes</a>)' }
	};

	$.ajax({
		url:"/setting"
	}).done(function(data){
		for (key in data) {
			if (key == 'keywords')
				continue;
			value = data[key];
			validate = null;
			name = key;
			if (key in fieldmap) {
				name = fieldmap[key]['caption'];
				if ('validate' in fieldmap[key])
					validate = fieldmap[key]['validate'];
			}
			$('#fields').append(name + '<br><input ' + (validate?'data-validate="true"':'') + ' type="text" name="' + key + '" value="' + value + '"><br>');
		}
		$('#fields').append('Photo keywords:<br><p id="keywords"></p>');
		$('#fields').append('<input type="text" id="keyword"><input type="button" id="add" value="Add keywords"><input type="button" id="test" value="Test keywords"><br>');
	});

	$("input[type='text']").change(function() {
		if ($(this).data('validate')) {
			$(this).val(fieldmap[this.name]['validate']($(this).val()));
		}
	});

}

function systemControls() {
	$("#reset").click(function() {
		if (confirm("Are you sure? Link to photos will also be reset")) {
			$.ajax({
				url:"/reset"
			}).done(function(){
				location.reload();
			});
		}
	});

	$("#reboot").click(function() {
		if (confirm("Are you sure you want to REBOOT?")) {
			$.ajax({
				url:"/reboot"
			}).done(function(){
				var newDoc = document.open("text/html", "replace");
				newDoc.write("<html><body><h1>Power off</h1></body></html>");
				newDoc.close();
			});
		}
	});

	$("#shutdown").click(function() {
		if (confirm("Are you sure you want to POWER OFF the frame?")) {
			$.ajax({
				url:"/shutdown"
			}).done(function(){
				var newDoc = document.open("text/html", "replace");
				newDoc.write("<html><body><h1>Power off</h1></body></html>");
				newDoc.close();
			});
		}
	});

}

function checkOAuth(funcContinue) {
	$.ajax({
		url:"/has/oauth"
	}).done(function(data){
		if (!data['result']) {
			$('#all').empty().append('You must provide OAuth2.0 details from Google, paste the JSON data into this box:<br><textarea style="width: 600px; height: 300px" id="oauth"></textarea><br><input type="button" id="authsubmit" value="Save"><hr>')
			$('#authsubmit').click(function() {
				$.ajax({
					url:"/oauth",
					type:"POST",
					data: $('#oauth').val(),
					contentType: "application/json; charset=utf-8",
					dataType: "json"
				}).done(function(data){
					location.reload();
				});
			});
		} else {
			funcContinue();
		}
	});
}

function checkLink(funcContinue) {
	$.ajax({
		url:"/has/token"
	}).done(function(data){
		if (data["result"]) {
			funcContinue();
		} else
			$('#all').empty().append('You need to link the photoframe to a Google Photos account<hr><input type="button" value="Link to Google Photos" id="link">')
			$('link').click(function(){
				location.href = "/link"
			});
	});
}

function getVersion(commit, date) {
	$.ajax({
		url:"/details/version"
	}).done(function(data){
		if (commit != null)
			$(commit).text(data["commit"]);
		if (date != null)
			$(date).text(data["date"]);
	});
}

TemplateEngine = function() {
	this.regTemplate = {}

	this.loadTemplate= function(templates, i, funcDone) {
		url = templates[i++];
		thiz = this;

		$.ajax({
			url:url
		}).done(function(data){
			thiz.regTemplate[url] = Handlebars.compile(data);
			if (i == templates.length)
				funcDone();
			else
				thiz.loadTemplate(templates, i, funcDone);
		})
	}
	
	this.load = function(templates, funcDone) {
		this.loadTemplate(templates, 0, funcDone);
	}

	this.get = function(url) {
		return this.regTemplate[url];
	}
}
