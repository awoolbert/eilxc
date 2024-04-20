// Information about this race that will be passed to the server when
// updating the database based on user actions on this page
var race = {
  race_id: $('#race_info').data('race_id'),
  group_id: $('#race_info').data('group_id'),
  race_number: $('#race_info').data('race_number'),
  races_count: $('#race_info').data('races_count'),
  prev_race_id: $('#race_info').data('prev_race_id'),
  next_race_id: $('#race_info').data('next_race_id'),
  gender: $('#race_info').data('gender'),
  is_jv: $('#race_info').data('is_jv'),
  name: $('#race_info').data('name')
};

// When races_count is selected, get the value, update the database and reload
$('#races_count-select').change(function() {
  var racesCount = $('option:selected', this).attr("data-races_count");
  race.races_count = racesCount;
  duplicateRace();
  location.reload();
});

// When gender is selected, get the value, update the database and reload
$('#gender-select').change(function() {
  console.log('went here');
  var gender = $('option:selected', this).attr("data-gender");
  gender = gender == 'combined' ? 'combo' : gender;
  race.gender = gender;

  // Since gender is changed, clear the existing selected_teams
  race.selected_teams = [];

  sendRaceDetail();
  location.reload();
});

// When is_jv is selected, get the value, update the database and reload
$('#is_jv-select').change(function() {
  var is_jv = $('option:selected', this).attr("data-is_jv");
  is_jv = is_jv == 'jv' ? true : false;
  race.is_jv = is_jv;

  sendRaceDetail();
  location.reload();
});

// When a team's checkbox is changed, make adjustments to lists, update the
// database accordingly then reload the page
$('.form-check-input').change(function() {
  team_id = $(this).attr("data-team_id");
  grabSelectedTeams();
  sendRaceDetail();
  location.reload();
});

// Functions to control the buttons which move runners from participating
// to non-participating
$(function() {

  function moveItems(origin, dest) {
    $(origin).find(':selected').appendTo(dest);
  }

  function moveAllItems(origin, dest) {
    $(origin).children().appendTo(dest);
  }

  $('.left').click(function() {
    tID = ($(this).closest('.team-container').attr('data-team_id'));
    origin = `#${tID}_participating-runners-select`;
    dest = `#${tID}_non-participating-runners-select`;
    moveItems(origin, dest);
    updateParticipantsList();
    sendParticipants();
    location.reload();
  });

  $('.right').on('click', function() {
    tID = ($(this).closest('.team-container').attr('data-team_id'));
    dest = `#${tID}_participating-runners-select`;
    origin = `#${tID}_non-participating-runners-select`;
    moveItems(origin, dest);
    updateParticipantsList();
    sendParticipants();
    location.reload();
  });

  $('.leftall').on('click', function() {
    tID = ($(this).closest('.team-container').attr('data-team_id'));
    origin = `#${tID}_participating-runners-select`;
    dest = `#${tID}_non-participating-runners-select`;
    moveAllItems(origin, dest);
    updateParticipantsList();
    sendParticipants();
    location.reload();
  });

  $('.rightall').on('click', function() {
    tID = ($(this).closest('.team-container').attr('data-team_id'));
    dest = `#${tID}_participating-runners-select`;
    origin = `#${tID}_non-participating-runners-select`;
    moveAllItems(origin, dest);
    updateParticipantsList();
    sendParticipants();
    location.reload();
  });
});

// If "edit team roster" link is selected, send to roster page
$('.edit-runner-link').click(function() {
  teamID = ($(this).closest('.team-container').attr('data-team_id'));
  window.location.href = `/${teamID}/roster/${race.race_id}/2`
});

// Enable tooltips
$(document).ready(function() {
  $('[data-toggle="tooltip"]').tooltip();
});

// update race name
$(document).ready(function() {
  $('#update-name-button').on('click', function() {
    race.name = $('#race-name-input').val();
    sendRaceDetail();
  });
});

// Function to loop through all of the select boxes to determine the
// participating runners and store them in the race object
const updateParticipantsList = () => {
  var participantsList = [];
  boxes = document.querySelectorAll('.participating-runners-select-box');
  boxes.forEach((box) => {
    for (var i = 0; i < box.options.length; i++) {
      participantsList.push(box.options[i].value);
    }
  });
  race.participants = participantsList;
};

// Function to grab the team_id of all selected teams from the DOM and
// store them in the race object
const grabSelectedTeams = () => {
  race.selected_teams = [];
  $('.form-check-input').each(function() {
    if ($(this).prop('checked')) {
      race.selected_teams.push($(this).attr("data-team_id"));
    }
  });
};

const previousPage = () => {
  if (race.race_number == 1) {
    window.location.href = "race_metadata";
  } else {
    // route to prev_race_id/race_detail
    var currentURL = (
      window.location.protocol 
      + "//" 
      + window.location.host 
      + window.location.pathname
    );
    var newURL = currentURL.replace(`/${race.race_id}/`,
      `/${race.prev_race_id}/`);
    window.location.replace(newURL);
  }
};

const finishRaceSetup = () => {
  // Add name to the race object and update the database
  race.name = $('#race-name-input').val();
  race.status = 'bib';
  sendRaceDetail();

  // Determine if this is the last race in the group
  if (race.race_number == race.races_count) {
    window.location.href = "using_bibs";
    // window.location.href = "assign_bibs"
  } else {
    // route to next_race_id/race_detail
    var currentURL = (
      window.location.protocol 
      + "//" 
      + window.location.host 
      + window.location.pathname
    );
    var newURL = currentURL.replace(`/${race.race_id}/`,
      `/${race.next_race_id}/`);
    window.location.replace(newURL);
  }
};

// AJAX call to update the database with the current participants
function sendParticipants() {
  $.ajax({
    async: false,
    url: '/update_race_participants',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race)
  });
  console.log(`Number of Participants: ${race.participants.length}`);
}

// AJAX call to update the database with the current state of the race
function sendRaceDetail() {
  $.ajax({
    async: false,
    url: '/update_race_detail',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race)
  });
}

// AJAX call to update the database to set group_id and
// create additional races if needed
function duplicateRace() {
  $.ajax({
    async: false,
    url: '/duplicate_race',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race)
  });
}

// Steps to be run upon load
grabSelectedTeams();
updateParticipantsList();
console.log('race:', race);
console.log(`Number of Participants: ${race.participants.length}`);
