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
          url:"/reboot"
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
          url:"/reboot"
        });
        $(document.body).html('<h1>Rebooting</h1>')
      }

    }
    console.log(data);
  });
});

$("#update").click(function() {
  if (confirm("Are you sure? This will reboot the frame")) {
    $.ajax({
      url:"/maintenance/update"
    }).done(function(){
      location.reload();
    });
  }
});

$("#reset").click(function() {
  if (confirm("Are you sure? Link to photos will also be reset")) {
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

$("input[class='search']").click(function(){
  window.open("https://photos.google.com/search/" + $(this).data('key'), "_blank");
});
$("input[class='delete']").click(function(){
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

$('#add').click(function(){
  $.ajax({
    url:"/keywords/" + $(this).data('service') + "/add",
    type:"POST",
    data: JSON.stringify({ keywords: $(this).prev("input[type=text]").val() }),
    contentType: "application/json; charset=utf-8",
    dataType: "json"
  }).done(function(data){
    location.reload();
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
    alert('Failed to upload the driver');
  }
});

$(".service-oauth").click(function() {
  alert("Please select JSON with client authentication data");
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
      location.reload();
    });
  }
});
