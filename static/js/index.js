/**
 * This file is part of photoframe (https://github.com/mrworf/photoframe).
 *
 * photoframe is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * photoframe is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with photoframe.  If not, see <http://www.gnu.org/licenses/>.
 */
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

	this.interval = function(input) {
		i = parseInt(input);
		if (i < 1 || isNaN(i))
			i = 1;
		if (i < 20)
			alert("Note! On RPi3, it typically takes 10s to preprocess the image, which can make <20s hard to maintain with consistency");
		return i.toString();
	}

	this.refresh = function(input) {
		i = parseInt(input);
		if (i < 0 || isNaN(i))
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

	this.minutes = function(input) {
		i = parseInt(input);
		if (i < 1 || isNaN(i))
			i = 1;
		return i.toString();
	}

	this.lux = function(input) {
		i = parseFloat(input);
		if (i < 0.01 || isNaN(i))
			i = 0.01;
		return i.toFixed(2).toString();
	}

	this.gpio = function(input) {
		i = parseInt(input);
		if (i < 0)
			i = 0;
		return i;
	}
}

Confirmation = function() {
	this.gpio = function() {
		var msg = 'WARNING!\n';
		   msg += '\n';
		   msg += 'Changing this setting can be potentially dangerous.\n';
		   msg += '\n';
		   msg += 'If the designated GPIO pin is already used for something else, it might cause your\n';
		   msg += 'device to shutdown at random. GPIO 26 is the default chosen for Raspberry Pi 3.\n';
		   msg += '\n';
		   msg += 'Please make sure you select an UNUSED gpio pin for your device before you continue.\n';
		   msg += '\n';
		   msg += 'Are you sure you want to change this value?';
		return confirm(msg);
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
	});

	$('#test').click(function(){
		var key = $('#keyword').val().trim()
		if (key != "")
			window.open("https://photos.google.com/search/" + encodeURIComponent(key), "_blank");
		else
			window.open("https://photos.google.com/", "_blank");
	});

}

var configData = [];
var configOutstanding = 0;

/**
 * Loads JSON from server and places data in configData
 * it also manages async behavior
 */
function loadConfigData(url, field, doneFunc)
{
	configOutstanding++;
	$.ajax({
		url: url
	}).done(function(data) {
		parts = field.split(',');
		if (parts.length == 3)
			configData[parts[0]][parts[1]][parts[2]] = data;
		else if (parts.length == 2)
			configData[parts[0]][parts[1]] = data;
		else
			configData[field] = data;
		configOutstanding--;
		if (configOutstanding == 0)
			doneFunc();
	}).fail(function(data) {
		alert('Problems loading ' + url + ' from backend, please reload');
		configOutstanding--;
		if (configOutstanding == 0)
			doneFunc();
	});
}

/**
 * Loads all relevant data into configData
 * in an async manner.
 */
function loadSettings(funcOk)
{
	funcTmp = function() {
		configOutstanding++;
		for (index in configData['service-defined']) {
			entry = configData['service-defined'][index];
			if (entry['useKeywords'])
				loadConfigData("/keywords/" + entry['id'], "service-defined," + index + ",keywords", funcOk);
		}
		configOutstanding--;
	}

	configOutstanding++; // Protect against early finish
	loadConfigData("/setting", "settings", funcTmp);
	loadConfigData("/details/sensor", "sensor", funcTmp);
	loadConfigData("/details/tvservice", "resolution", funcTmp);
	loadConfigData("/details/timezone", "timezones", funcTmp);
	loadConfigData("/details/drivers", "drivers", funcTmp);
	loadConfigData("/details/version", "version", funcTmp);

	loadConfigData("/service/available", 'service-available', funcTmp);
	loadConfigData("/service/list", 'service-defined', funcTmp);
	configOutstanding--;
}

TemplateEngine = function() {
	window.Handlebars.registerHelper('select', function( value, options ){
		var $el = $('<select />').html( options.fn(this) );
		$el.find('[value="' + value + '"]').attr({'selected':'selected'});
		return $el.html();
	});

	window.Handlebars.registerHelper('ifvalue', function(conditional, options) {
		if (options.hash.value === conditional) {
			return options.fn(this);
		} else {
			return options.inverse(this);
		}
	});

	window.Handlebars.registerHelper('encode', function(value, options) {
		return encodeURIComponent(value);
	});

	this.regTemplate = {}

	this.loadTemplate= function(templates, i, funcDone) {
		url = templates[i++];
		thiz = this;

		$.ajax({
			url:'template/' + url,
			cache: false
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
