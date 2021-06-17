$('#driver').fileupload({
  add: function (e, data) {
    $('#driver-button').prop('disabled', 'disabled');
    data.submit();
  },
  done: function (e, data) {
    console.log(data);
    if (data.result['reboot']) {
      if(confirm('In order to fully enable this change, you must reboot the photoframe. Do you wish to do this now?')) {
        $.ajax({
          url:"/maintenance/reboot"
        });
        rebootWatch();
      } else {
        alert("Upload complete, refreshing drivers");
        location.reload();
      }
    } else {
      alert("Upload complete, refreshing drivers");
      location.reload();
    }
  },
  fail: function (e, data) {
    alert('Failed to upload the driver');
  },
  always: function(e, data) {
    $('#driver-button').prop('disabled', '');
  }
});

$("#driver-button").click(function() {
  $('#driver').trigger('click');
});

function rebootWatch() {
  $(document.body).html('<h1>Restarting<span id="reboot"></span></h1>Please be patient, this can take anywhere from 30s to several minutes depending on device and network.<br><br>Page will automatically refresh once photoframe is available again')
  setTimeout(rebootWatchCheck, 10000); // Wait 10s, since nothing will be up that fast anyway (also solves issues during update)
}

function rebootWatchCheck() {
  $.ajax({
    url:"/setting",
    type:"GET",
  }).done(function(e, data){
    document.location.reload();
  }).fail(function(e, data) {
    setTimeout(rebootWatchCheck, 5000);
    if ($('#reboot').text() == '...')
      $('#reboot').text('');
    else
      $('#reboot').append('.');
  });
}

// Refresh image every 30s
function reloadScreen() {
  $('#screen').attr('src', "/details/current?" + new Date().getTime())
  reloadScreenTimeout = setTimeout(reloadScreen, 30000);
}
reloadScreen();

$(".slideshowControl").click(function () {
  $.ajax({
    url: "/control/" + $(this).attr("id")
  }).done(function (){
    //update thumbnail image
    clearTimeout(reloadScreenTimeout);
    reloadScreenTimeout = setTimeout(reloadScreen, 3000);
  });
});

function updateAmbient() {
  $.ajax({
    url:'/details/color'
  }).done(function(data) {
    if (data['temperature'] == null)
    return;

    $('#colortemp').text(data['temperature'].toFixed(0));
    $('#lux').text(data['lux'].toFixed(2));
    setTimeout(updateAmbient, 5000);
  });
}
updateAmbient();

function disableSlideshowControls(){
  if ($("select[name=randomize_images]").val() == "1") {
    $("#prevAlbum").prop('disabled', true);
    $("#prevAlbum").prop('title', "disable 'randomize image order'")
    $("#nextAlbum").prop('disabled', true);
    $("#nextAlbum").prop('title', "disable 'randomize image order'")
  }
  else {
    $("#prevAlbum").prop('disabled', false);
    $("#prevAlbum").prop('title', "")
    $("#nextAlbum").prop('disabled', false);
    $("#nextAlbum").prop('title', "")
  }
}
disableSlideshowControls()

valid = new Validator();
confirmation = new Confirmation();

$("input[type='text']").change(function() {
  if ($(this).attr('name') == undefined)
  return;

  if ($(this).attr('name') == 'hostname') {
    thiz = this;
    if (confirm('Are you sure you whish to change the name of the frame?')) {
      $.ajax({
        url: '/options/hostname/' + encodeURIComponent($(this).val())
      }).done(function(data) {
        if (data['hostname'] !== $(thiz).val())
          alert('Note!\n\nSome characters in the name were not allowed\n\nOnly A through Z and 0 through 9 (and dashes) are allowed.\nMax 63 characters');
        configData['hostname']= data;
        $(thiz).val(configData['hostname'].hostname);
        window.document.title = configData.hostname.hostname
      }).fail(function(data) {
        alert('Unable to change hostname');
        $(thiz).val(configData['hostname'].hostname);
      });
    } else {
      $(this).val(configData['hostname'].hostname);
    }
    return;
  }

  confirmit = $(this).data('confirm');
  if (confirmit && !eval('confirmation.' + confirmit + '()')) {
    // Yeah, not pretty, but easier
    document.location.reload();
    return;
  }
  validate = $(this).data('validate');
  if (validate) {
    $(this).val(eval('valid.' + validate + '($(this).val());'));
  }
  console.log("/setting/" + $(this).attr('name') + "/" + $(this).val());
  $.ajax({
    url:"/setting/" + $(this).attr('name') + "/" + $(this).val(),
    type:"PUT"
  }).done(function(){
  });
});

$("select[name=powersave]").change(function() {
  $.ajax({
    url:"/setting/" + $(this).attr('name') + "/" + encodeURIComponent($(this).val()),
         type:"PUT"
  }).done(function(){
  });
});

$("select[name=display-rotation]").change(function() {
  $.ajax({
    url:"/rotation/" + $(this).val(),
         type:"PUT"
  }).done(function(){
    if(confirm('In order to fully enable this change, you must reboot the photoframe. Do you wish to do this now?')) {
      $.ajax({
        url:"/maintenance/reboot"
      });
      rebootWatch();
    }
  });
});

$("select[name=display-overscan]").change(function() {
  $.ajax({
    url:"/overscan/" + $(this).val(),
         type:"PUT"
  }).done(function(){
    if(confirm('In order to fully enable this change, you must reboot the photoframe. Do you wish to do this now?')) {
      $.ajax({
        url:"/maintenance/reboot"
      });
      rebootWatch();
    }
  });
});

$("select[name=force_orientation]").change(function () {
  var value = $(this).val()
  $.ajax({
    url: "/setting/" + $(this).attr('name') + "/" + encodeURIComponent($(this).val()),
    type: "PUT"
  }).done(function (){
  });
});

$("select[name=imagesizing]").change(function() {
  $.ajax({
    url:"/setting/" + $(this).attr('name') + "/" + encodeURIComponent($(this).val()),
    type:"PUT"
  }).done(function(){
  });
});

$("select[name=randomize_images]").change(function () {
  $.ajax({
    url: "/setting/" + $(this).attr('name') + "/" + encodeURIComponent($(this).val()),
    type: "PUT"
  }).done(function () {
    disableSlideshowControls();
  });
});

$("select[name=enable-cache]").change(function () {
  $.ajax({
    url: "/setting/" + $(this).attr('name') + "/" + encodeURIComponent($(this).val()),
    type: "PUT"
  }).done(function () {
  });
});

$("select[name=offline-behavior]").change(function () {
  $.ajax({
    url: "/setting/" + $(this).attr('name') + "/" + encodeURIComponent($(this).val()),
    type: "PUT"
  }).done(function () {
  });
});

$("select[name=tvservice]").change(function() {
  $.ajax({
    url:"/setting/tvservice/" + encodeURIComponent($(this).val()),
    type:"PUT"
  }).done(function(){
  });
});

$("select[name=timezone]").change(function() {
  $.ajax({
    url:"/setting/timezone/" + encodeURIComponent($(this).val().replace('/', '+')),
    type:"PUT"
  }).done(function(){
  });
});

$("select[name=display-driver]").change(function() {
  $.ajax({
    url:"/setting/display-driver/" + encodeURIComponent($(this).val()),
    type:"PUT"
  }).done(function(data){
    if (data['status']) {
      if(confirm('In order to fully enable this change, you must reboot the photoframe. Do you wish to do this now?')) {
        $.ajax({
          url:"/maintenance/reboot"
        });
        rebootWatch();
      }
    }
    console.log(data);
  });
});

$("#update").click(function() {
  $.ajax({
    url:"/maintenance/checkversion"
  }).done(function(data) {
    if (data.checkversion) {
      var msg = "New version was found\n\nThis will force an update of the photoframe and cause a restart.\n\nDo you want to continue?";
      if (confirm(msg)) {
        $.ajax({
          url:"/maintenance/update"
        }).done(function(){
          rebootWatch();
        });
      }
    } else {
      if (confirm('No new version is available, would you like to see current version information?')) {
        $.ajax({
          url:"/details/version"
        }).done(function(data){
          msg = 'Last change to codebase was ' + data.date + "\n\n";
          msg += 'Running variant "' + data.branch + '"';
          if (data.branch != 'master')
            msg += ' (unsupported)';
          msg += '\n\nChange id: ' + data.commit;
          alert(msg);
        });
      }
    }
  });
});

$("#reset").click(function() {
  if (confirm("Are you sure?\n\nThis will remove any and all changes to the photoframe and it will behave as if you just installed it. Once you accept, you cannot undo and will have to reconfigure the photoframe again.\n\nNote! This will cause the photoframe to reboot")) {
    $.ajax({
      url:"/maintenance/reset"
    }).done(function(){
      location.reload();
    });
  }
});

$("#clearCache").click(function () {
  if (confirm("Are you sure you want to REMOVE ALL CACHED IMAGES on your device?")) {
    $.ajax({
      url: "/maintenance/clearCache"
    }).done(function () {
    });
  }
});

$("#forgetMemory").click(function () {
  if (confirm("Are you sure you want to FORGET ALL IMAGES that have already been displayed?")) {
    $.ajax({
      url: "/maintenance/forgetMemory"
    }).done(function () {
    });
  }
});

$("#debug").click(function() {
  location = "/debug";
});

$("#reboot").click(function() {
  if (confirm("Are you sure you want to REBOOT?")) {
    $.ajax({
      url:"/maintenance/reboot"
    });
    rebootWatch();
  }
});

$("#backup").click(function() {
  if (confirm("Backup current settings to /boot/settings.tar.gz ?")) {
    $.ajax({
      url:"/maintenance/backup"
    }).done(function (){
    });
  }
});

$("#restore").click(function() {
  if (confirm("This will remove the current configuration and restore saved settings from /boot/settings.tar.gz ?")) {
    $.ajax({
      url:"/maintenance/restore"
    }).done(function(){
      rebootWatch();
    });
  }
});

$("#dnldcfg").click(function() {
  window.location.assign("/maintenance/dnldcfg")
});

$("#upldcfg").click(function() {
  if (confirm("Upload settings.tar.gz from this device?")) {
    $.ajax({
      url:"/upload/config"
    }).done(function(){
      rebootWatch();
    });
  }
});

$('#config').fileupload({
  add: function (e, data) {
    $('#config-button').prop('disabled', 'disabled');
    data.submit();
  },
  done: function (e, data) {
    console.log(data);
    if (data.result['reboot']) {
      $.ajax({
        url:"/maintenance/reboot"
      });
    } else {
      alert("Failed to install configuration - is the file OK?");
      location.reload();
    }
  },
  fail: function (e, data) {
    alert('Failed to upload configuration');
  },
  always: function(e, data) {
    $('#driver-button').prop('disabled', '');
  }
});

$("#config-button").click(function() {
  $('#config').trigger('click');
});

$("#shutdown").click(function() {
  if (confirm("Are you sure you want to POWER OFF the frame?")) {
    $.ajax({
      url:"/maintenance/shutdown"
    });
    $(document.body).html('<h1>Powering off</h1>')
  }
});

$("input[class='keyword-search']").click(function(){
  window.open("/keywords/" + $(this).data('service') + '/source/' + $(this).data('index'), "_blank");
});
$("input[class='keyword-details']").click(function(){
  console.log('Show details');
  $('#details_short').html('Loading...');
  $('#details_long').html('Loading...');
  $('#help_details').show();
  $("button[name=details_close]").click(function() {
    $(this).parent().parent().hide();
  });
  $.ajax({
    url:"/keywords/" + $(this).data('service') + "/details/" + $(this).data('index')
  }).done(function(data){
    $('#details_short').text(data.short);
    str = "";
    for (line in data.long) {
      str += data.long[line] + "\n";
    }
    $('#details_long').text(str);
  });
  //window.open("/details.html?service=" + $(this).data('service') + '&index=' + $(this).data('index'), "_blank");
});
$("input[class='keyword-delete']").click(function(){
  if (confirm("Are you sure?")) {
    $.ajax({
      url:"/keywords/" + $(this).data('service') + "/delete",
      type:"POST",
      data: JSON.stringify({ id: $(this).data('index') }),
      contentType: "application/json; charset=utf-8",
      dataType: "json"
    }).done(function(data){
      location.reload();
    });
  }
});

$('.keyword').keypress(function (e) {
  if (e.which == 13) {
    $(this).next(".keyword-add").trigger("click");
    return false;
  }
});

$('.keyword-add').click(function(){
  $('#busy').show();
  $.ajax({
    url:"/keywords/" + $(this).data('service') + "/add",
    type:"POST",
    data: JSON.stringify({ keywords: $(this).prev("input[class=keyword]").val() }),
    contentType: "application/json; charset=utf-8",
    dataType: "json"
  }).done(function(data){
    $('#busy').hide();
    if (!data.status) {
      alert('Failed to add keyword:\n\n' + data.error);
    } else {
      location.reload();
    }
  });
});

$('.keyword-help').click(function(){
  $.ajax({
    url:"/keywords/" + $(this).data('service') + "/help",
    type:"GET",
  }).done(function(data){
    alert(data['message']);
  });
});



$("#new-service").click(function() {
  var name = prompt('Please provide a nickname for ' + $('#new-service-type option:selected').text(), $('#new-service-type option:selected').text());
  name = name.trim();
  if (name == '')
    alert('Aborted');
  else {
    $.ajax({
      url:"/service/add",
      type:"POST",
      data: JSON.stringify({ "name": name, "id": $('#new-service-type').val() }),
      contentType: "application/json; charset=utf-8",
      dataType: "json"
    }).done(function(data){
      location.reload();
    });
  }
});

$('.oauth-json').fileupload({
  add: function (e, data) {
    data.submit();
  },
  done: function (e, data) {
    //console.log(data);
    // Trigger linking
    var service = $(this).next().data('service');
    location = '/service/' + service + '/link';
  },
  fail: function (e, data) {
    alert('Failed to authorize due to:\n' + data.jqXHR.responseText);
  }
});

$(".service-oauth").click(function() {
  // Disable alert since it breaks chrome and ie
  //alert("In the following file selector, please select the JSON file you donwloaded with client authentication data.\n\nIf you don't get a file selector, please make sure you don't have any adblockers blocking this website.");
  $(this).prev().trigger('click');
});

$(".service-delete").click(function() {
  if (confirm("Are you sure?")) {
    $.ajax({
      url:"/service/remove",
      type:"POST",
      data: JSON.stringify({ "id": $(this).data('service') }),
      contentType: "application/json; charset=utf-8",
      dataType: "json"
    }).done(function(data){
      console.log(data);
      location.reload();
    });
  }
});

$('#explain_imagesizing').click(function() {
  console.log('Show help');
  $('#help_imagesizing').show();
});

$("button[name=help_close]").click(function() {
  $(this).parent().parent().hide();
});
