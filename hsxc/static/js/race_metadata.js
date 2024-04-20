// Information about this race that will be passed to the server when
// updating the database based on user actions on this page
let $raceInfo = $('#race_info');

let race = {
  race_id: $raceInfo.data('race_id'),
  host_school_id: $raceInfo.data('host_school_id'),
  location_id: $raceInfo.data('location_id'),
  course_id: $raceInfo.data('course_id'),
  group_id: $raceInfo.data('group_id'),
  date: $raceInfo.data('date'),
};
console.log(race);

// When host school is selected, get the value, update the database and reload
$('#host-school-select').on('change', function() {
  let hostSchoolID = $(this).find('option:selected').data('host_school_id');

  // if user wants to add a new school, route to add_school
  if (hostSchoolID == 'add') {
    window.location.href = "add_school";
  } else {
    race.host_school_id = hostSchoolID;
    ['location_id', 'course_id'].forEach(prop => delete race[prop]);
    sendRaceData();
    location.reload();
  }
});

// When location selected, get value, update database and reload
$('#location-select').on('change', function() {
  let locationID = $(this).find('option:selected').data('location_id');

  if (locationID === 'add') {
    window.location.href = "add_location";
  } else {
    race.location_id = locationID;
    delete race.course_id;
    sendRaceData();
    location.reload();
  }
});

// When course selected, get value, update database and reload
$('#course-select').on('change', function() {
  let courseID = $(this).find('option:selected').data('course_id');

  if (courseID === 'add') {
    window.location.href = "add_course";
  } else {
    race.course_id = courseID;
    sendRaceData();
    location.reload();
  }
});

// on clicking edit button, populate the modal with that runner's info


// Enable tooltip
$(document).ready(function(){
  $('[data-toggle="tooltip"]').tooltip();
});

// Add event listeners to the participating schools buttons.  Each time a
// button is pressed, move the items in the DOM, grab the participating
// schools and update the database accordingly.  Display the next page
// button if a school is added to the list and it is not yet displayed
$(function () {

  function sortSelect(selElem) {
    let selected = $(selElem).val(); // preserving original selected values
    $(selElem).html($("option", $(selElem)).sort(function(a, b) {
        return a.text == b.text ? 0 : a.text < b.text ? -1 : 1
    }));
    $(selElem).val(selected); // restoring original selected values
  }  

  function moveItems(origin, dest) {
    $(origin).find(':selected').appendTo(dest);
    sortSelect(dest);
  }

  function moveAllItems(origin, dest) {
      $(origin).children().appendTo(dest);
      sortSelect(dest);
  }

  $('#left').click(function () {
      moveItems('#selected-school-select', '#possible-school-select');
      grabParticipatingSchools();
      sendRaceData();
  });

  $('#right').on('click', function () {
      moveItems('#possible-school-select', '#selected-school-select');
      grabParticipatingSchools();
      sendRaceData();
      addNextPageButton();
  });

  $('#leftall').on('click', function () {
      moveAllItems('#selected-school-select', '#possible-school-select');
      grabParticipatingSchools();
      sendRaceData();
  });

  $('#rightall').on('click', function () {
      moveAllItems('#possible-school-select', '#selected-school-select');
      grabParticipatingSchools();
      sendRaceData();
      addNextPageButton();
  });
});

// Function to get the list of participating schools from the DOM
const grabParticipatingSchools = () => {
  var pSchools = document.getElementById("selected-school-select");
  var tempSchools = [];
  if (pSchools) {
    for(var i = 0; i < pSchools.options.length; i++) {
      tempSchools.push(pSchools.options[i].value);
    }
  }
  race.schools = tempSchools;
  if (pSchools) {
    if (pSchools.options.length > 1) {
      addNextPageButton();
    }
  }
};

// Function to add the next page button when appropriate
function addNextPageButton () {
  html = `<div class="container mt-3 mb-5" id="next-page-btn">
    <button class="btn btn-primary btn-block" onclick="nextPage();">
      Continue
    </button>
  </div>`
  if (!document.getElementById("next-page-btn")) {
    el = document.getElementById("race_info");
    el.insertAdjacentHTML('beforeend', html);
  }
};

function nextPage () {
  race.status = 'setup';
  sendRaceData();
  window.location.href = "race_detail";
};

// AJAX call to update the database on the server with the current state of
// the race
function sendRaceData() {
  $.ajax({
    async: false,
    url: '/update_race_metadata',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race)
  });
}

// Initialize the datepicker
$('#datepicker').datepicker({autoclose: true,
                              todayHighlight: true});
$('#datepicker').on('changeDate', function() {
    $('#datepicker').val(
        $('#datepicker').datepicker('getFormattedDate')
    );
    race.date = $('#datepicker').val();
    if (race.host_school_id) {
      sendRaceData();
    }
});

// Calling this on load so that race object populates with participating
// schools if they are present
grabParticipatingSchools();
