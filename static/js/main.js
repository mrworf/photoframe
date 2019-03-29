// Refresh image every 30s
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
  $(document.body).html('<h1>Rebooting</h1>')
}

function reloadScreen() {
  $('#screen').attr('src', "/details/current?" + new Date().getTime())
  setTimeout(reloadScreen, 30000);
}
reloadScreen();

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

valid = new Validator();
confirmation = new Confirmation();

$("input[type='text']").change(function() {
  if ($(this).attr('name') == undefined)
    return;

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
    url:"/details/version"
  }).done(function(data) {
    console.log(data);
    var msg = "Are you sure?\n\nThis will force the photoframe to look for a new version and reboot.\n\nNote! Even if no new version is found, photoframe will still reboot.";
    /* NOT VERY USEFUL YET
    msg += "\n\nCurrent version information:\n";
    msg += 'Commit ' + data.commit + '(' + data.branch + ')\n';
    msg += 'Dated ' + data.date;
    */
    if (confirm(msg)) {
      $.ajax({
        url:"/maintenance/update"
      }).done(function(){
        location.reload();
      });
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

$("#reboot").click(function() {
  if (confirm("Are you sure you want to REBOOT?")) {
    $.ajax({
      url:"/maintenance/reboot"
    });
    rebootWatch();
  }
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
