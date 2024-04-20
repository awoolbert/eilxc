// get the race_id and put it in race object to be sent to server
var race = {
  race_id: $('#race_info').data('race_id'),
};


// Enable tooltips
$(document).ready(function(){
  $('[data-toggle="tooltip"]').tooltip();
});


// return to previous page (race_detail)
const previousPage = () => {
  window.location.href = "race_detail";
};


// Function to display the bib assignment section of the page once a team
// is selected
function displaySchoolParticipants(school_id) {
  // get the selected school's name and colors
  for(var i = 0; i < race.schools.length; i++) {
    if (race.schools[i].school_id == school_id) {
      schoolName = race.schools[i].school_name;
      primaryColor = race.schools[i].primary_color;
      textColor = race.schools[i].text_color;
    }
  }

  // group by gender and alphabetize participants before displaying
  race.participants.sort((a, b) => 
    (a.runner_last_name + a.runner_first_name 
     > b.runner_last_name + b.runner_first_name) 
     ? 1 : -1);
  race.participants.sort((a, b) => (a.gender > b.gender) ? -1 : 1);

  // build html for the bib assignment inputs and buttons and place in DOM
  bibNumbersHTML = `
  <h5>Enter range of bib numbers available to assign:</h5>
  <div id="alerts"></div>
  <form>
    <div class="form-row ml-3">

      <div class="col-2">
        <input 
          id="bibMin" 
          type="text" 
          class="form-control" 
          placeholder="Min Bib No."
        >
      </div>

      <div class="col-2">
        <input 
          id="bibMax" 
          type="text" 
          class="form-control" 
          placeholder="Max Bib No."
        >
      </div>

      <div class="col-2">
        <button 
          id="assign-btn" 
          type="button" 
          class="btn btn-primary" 
          name="assign-btn" 
          onclick="assignNumbers();"
        >
          Assign This School
        </button>
      </div>

      <div class="col-2">
        <button 
          id="assign-all-btn" 
          type="button" 
          class="btn btn-primary" 
          name="assign-all-btn" 
          onclick="assignNumbers(all=true);"
        >
          Assign All Schools
        </button>
      </div>

      <div class="col-2 offset-2">
        <button 
          id="remove-btn" 
          type="button" 
          class="btn btn-danger" 
          name="remove-btn" 
          onclick="removeNumbers();"
        >
          Clear Existing
        </button>
      </div>

      <div id="alerts"></div>

      </div>

    <small class="muted ml-4">
      Enter the range of bib numbers you have to allocate among the teams
    </small>

    </form>
  `;
  $('#bib-numbers-ctr').html(bibNumbersHTML);

  // check if all runners on this team already have bibs
  var teamMissingBib = 0;
  var raceMissingBib = 0;
  race.participants.forEach(p => {
    if (p.bib == null) {
      raceMissingBib++;
      if (p.school_id == school_id) {
        teamMissingBib++;
      }
    }
  });

  // build html for the empty table of runners and place in DOM
  bibAssignHTML = `
  <table class="table table-sm table-striped mb-4 ml-4">
    <thead>
      <tr>
        <th scope="col" class="text-center">School</th>
        <th scope="col" class="text-center">Team</th>
        <th scope="col">First</th>
        <th scope="col">Last</th>
        <th scope="col">Bib</th>
        <th scope="col">Edit</th>
      </tr>
    </thead>
    <tbody id="runner-list" data-school_id="${school_id}">
    </tbody>
  </table>
  `;
  $('#bib-assign-ctr').html(bibAssignHTML);

  // add the appropriate buttons to the page based on how much is complete
  $('#middle-btn').html('');
  $('#right-btn').html('');
  var middleBtnHTML = '';
  var rightBtnHTML = '';
  if (teamMissingBib == 0) {
    middleBtnHTML = `
      <button 
        id="emailAssignmentsBtn" 
        class="btn btn-success" 
        type="button" 
        name="button" 
        onclick="showEmailModal();"
      >
        Email Bib Assignments
      </button>
    `;
    $('#middle-btn').html(middleBtnHTML);
  }
  if (raceMissingBib == 0) {
    rightBtnHTML = `
      <button 
        id="finishBtn" 
        class="btn btn-primary" 
        type="button" 
        name="button" 
        onclick="finishBibAssignment();"
      >
        Next Page >>
      </button>`;
    $('#right-btn').html(rightBtnHTML);
  }

  // fill the empty table of runners with runners
  race.participants.forEach((p) => {
    if (p.school_id == school_id){
      runnerHTML = `
        <tr 
          class="runner" 
          data-result_id="${p.result_id}" 
          data-bib="${p.bib == null ? '' : p.bib}" 
          data-name="${p.runner_first_name} ${p.runner_last_name}"
        >
          <td 
            class="text-center" 
            style="background-color:${primaryColor}; 
                  color:${textColor}">${schoolName}
          >
          </td>
          
          <td class="text-center">${p.gender == 'boys' ? 'M' : 'F'}</td>
          <td>${p.runner_first_name}</td>
          <td>${p.runner_last_name}</td>
          <td class="bib">${p.bib == null ? '' : p.bib}</td>
          
          <td class="actions">
            <a 
              href="" 
              class="edit-bib" 
              data-placement="top" 
              title="Click to manually edit number"
            >
              <i class="material-icons">edit</i>
            </a>
          </td>

        </tr>
      `;
      $('#runner-list').append(runnerHTML);
    }
  });
  console.log(`selected: ${schoolName}`);
};


// Function to edit the bib number of a specific runner
var editInProgress = false; // starting condition on load
$(document).on('click','.edit-bib',function(e){
  e.preventDefault();

  // If an edit is already in progress, return, else continue
  if (editInProgress) {return;}

  // Set editInProgress to true to disable other edit buttons
  editInProgress = true;

  // Get the row associated with the edit button
  resRow = $(this).closest('tr');

  // Update the DOM with the input box and update button
  bibEditInputHTML = `
    <input 
      class="bibEditInput" 
      size="5" 
      value="${resRow.data('bib')}" 
      autofocus
    >
    </input>
  `;
  updateBtnHTML = `
  <div class="btn btn-sm btn-primary bibUpdateBtn">Update</btn>
  `;
  resRow.children('.bib').first().html(bibEditInputHTML);
  resRow.children('.actions').first().html(updateBtnHTML);

});


$(document).on('click', '.bibUpdateBtn' ,function(e) {
  // Get the row associated with the update button and get info on result
  resRow = $(this).closest('tr');
  result_id = parseInt(resRow.data('result_id'));

  // Get user input, set a blank value to null
  var newBib = (
    $('.bibEditInput').val() == '' 
    ? null 
    : parseInt($('.bibEditInput').val())
  );

  // Confirm newBib is a number
  if(isNaN(newBib) && newBib != null) {
    invalidBibsModal('Entry Error', 'Please enter a valid number and retry');
    return;
  }

  // Confirm newBib isn't already taken
  foundDuplicate = false;
  race.participants.forEach((p,i) => {
    if (p.result_id == result_id) {
      participantsIndex = i;
    } else if (p.bib == newBib) {
      invalidBibsModal(
        'Entry Error', 
        'This bib number is already assigned to another runner.  Please retry'
      );
      foundDuplicate = true;
    }
  });
  if (foundDuplicate) {return;}

  // Update the race object with the new bib number
  race.participants[participantsIndex].bib = newBib;

  // Allow for other edit buttons to be selected
  editInProgress = false;

  // update the database with the bib assignements
  sendBibAssignments();

  // update the DOM to display bib assignement
  displaySchoolParticipants($('#runner-list').data('school_id'));

});


// function to display the next page button if all runners have bibs
function displayNextPageButton() {
  // check if all runners have bibs
  var raceMissingBib = 0;
  race.participants.forEach(p => {
    if (p.bib == null) {
      raceMissingBib++;
    }
  });

  // display button if all assigned
  if (raceMissingBib == 0) {
    rightBtnHTML = `
      <button 
        id="finishBtn" 
        class="btn btn-primary" 
        type="button" 
        name="button" 
        onclick="finishBibAssignment();"
      >
        Next Page >>
      </button>`;
    $('#right-btn').html(rightBtnHTML);
  }
};


// function to display alert for impropper bib range
function addAlert(message) {
    $('#alerts').append(
        '<div class="alert alert-danger">' +
            '<button type="button" class="close" data-dismiss="alert">' +
            '&times;</button>' + message + '</div>');
}


// function to display an error modal if bib number inputs are invalid
function invalidBibsModal(title, message) {
  $('#invalidBibsModal').modal('show');
  $('#invalidBibsModalTitle').html(title);
  $('#invalidBibsModalBody').html(message);
};


// validate number range provided, assign numbers to runners, update database
function assignNumbers(all=false) {
  // get numbers from DOM
  bibMin = parseInt($('#bibMin').val());
  bibMax = parseInt($('#bibMax').val());
  runnerCount = $('.runner').length;

  // build list of bibs already assigned
  usedBibs = [];
  race.participants.forEach((p) => {
    if (p.bib) {
      usedBibs.push(p.bib);
    }
  });

  // warn if both are not numbers
  if (isNaN(bibMin) || isNaN(bibMax)) {
    invalidBibsModal('Entry Error', 'Please enter two valid numbers and retry');
    return;
  }

  // warn if min < max
  if (bibMin > bibMax) {
    invalidBibsModal(
      'Entry Error', 
      'Please ensure minimum bib number is less than maximum and retry'
    );
    return;
  }

  // build list of bibs to be assigned based on range
  bibsToAssign = []
  for (var i = bibMin; i < bibMax + 1; i++) {
    bibsToAssign.push(i);
  }

  // remove any usedBibs from bibsToAssign, warn if not enough bibs
  var sendAlert = 0;
  for (var i = bibsToAssign.length - 1; i >= 0; i--) {
    if (usedBibs.includes(bibsToAssign[i])) {
      bibsToAssign.splice(i,1)
      sendAlert++;
    }
  }
  if (sendAlert > 0) {
    if (bibsToAssign.length < runnerCount) {
      invalidBibsModal(
        'Entry Error', 
        `Some of these bib numbers are already allocated to other teams, 
        leaving insufficient bib numbers. You have ${bibsToAssign.length} 
        unassigned bibs available for ${runnerCount} runners. Please retry`
      );
      return;
    }
  }

  // warn if there are not enough bibs
  if (bibsToAssign.length < runnerCount) {
    invalidBibsModal(
      'Entry Error', 
      `Not enough bibs. You have ${bibsToAssign.length} bibs for ${runnerCount} 
      runners. Please retry`
    );
    return;
  }

  // get the result ids for each runner displayed
  resIDs = getResIDs();

  // update the race object with bib assignments and display
  if (all) {
    race.schools.forEach(s => {
      race.participants.forEach(p => {
        if (s.school_id == p.school_id) {
          p.bib = bibsToAssign.splice(0,1)[0];
        }
      });
    });
  }
  else {
    race.participants.forEach(p => {
      if (resIDs.includes(p.result_id)) {
        if (p.bib === null) {
          p.bib = bibsToAssign.splice(0,1)[0];
        }
      }
    });
  }

  console.log(race);

  // update the database with the bib assignements
  sendBibAssignments();

  // update the DOM to display bib assignement
  displaySchoolParticipants($('#runner-list').data('school_id'));
};


// function to remove bib numbers from this group of runners
function removeNumbers() {
  // get the result ids for each runner displayed
  resIDs = getResIDs();

  // update the race object with bibs assigned to null and display
  race.participants.forEach(p => {
    if (resIDs.includes(p.result_id)) {
      p.bib = null;
    }
  });
  console.log(race);

  // update the database with the bib assignements
  sendBibAssignments();

  // update the DOM to display bib assignement
  displaySchoolParticipants($('#runner-list').data('school_id'));
};


// Helper function to get the result_ids for the runners currently displayed
function getResIDs() {
  resIDs = [];
  $('.runner').each(function(index, result) {
    resIDs.push(parseInt($(result).data('result_id')));
  });
  return resIDs;
};


// show email modal when button is pressed
function showEmailModal() {
  // show modal
  $('#emailBibsModal').modal('show');

  // get the name of the school
  race.schools.forEach((s, i) => {
    if (s.school_id == $('#runner-list').data('school_id')) {
      school_name = s.school_name;
    }
  });

  // build title and display in DOM
  title = `Email Bib Assignments for ${school_name}`;
  $('#emailBibsModalTitle').html(title);
};


// Every time a modal is shown, if it has an autofocus element, focus on it.
$('.modal').on('shown.bs.modal', function() {
  $(this).find('[autofocus]').focus();
});


// Function to send email with bib assignments
function sendEmail() {
  // get the user input email
  email = $('#emailInput').val();

  // confirm a valid email address has been entered and warn if not
  atIndex = email.indexOf('@')
  // has no @ or has an @ which is too close to the beginning or end
  if (atIndex <= 0 || atIndex >= email.length - 4) {
    $('#emailBibsModal').modal('hide');
    invalidBibsModal(
      'Error: Invalid email address', 
      'You have entered an invalid email address.  Please try again.'
    );
    return;
  }
  // has no dot or has a dot too close to the end
  dotIndex = email.substring(atIndex+1).indexOf('.');
  if (dotIndex == -1 || dotIndex >= email.substring(atIndex+1).length -2) {
    $('#emailBibsModal').modal('hide');
    invalidBibsModal(
      'Error: Invalid email address', 
      'You have entered an invalid email address.  Please try again.'
    );
    return;
  }

  // add email address to the emailObject
  var emailObject = {'recipients': email};

  // build the message body and add it to the emailObject
  var school_id = $('#runner-list').data('school_id');

  // get the name of the school
  race.schools.forEach((s, i) => {
    if (s.school_id == school_id) {
      school_name = s.school_name;
    }
  });

  messageBody = `Below are the bib assignments for ${school_name}: \r\n\r\n`;
  messageBody += 'Bib     Runner\r\n';
  messageBody += '---     --------------------';
  $('.runner').each(function() {
    bib = $(this).data('bib');
    runnerName = $(this).data('name');
    messageBody += '\r\n'
    messageBody += `${bib}${' '.repeat(11-bib.toString().length*2)}${runnerName}`;
  });

  messageBody += `\r\n\r\nGood luck runners!`;

  emailObject.messageBody = messageBody;
  emailObject.race_id = race.race_id;

  // send the email address and message content to the server to be mailed
  $.ajax({
    async: true,
    url: '/email_bib_assignments',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(emailObject),
  });

  $('#emailBibsModal').modal('hide');

};

// Function to set races status to ready and return to home
function finishBibAssignment() {
  race.status = 'ready';
  // ajax call to set status to ready
  $.ajax({
    async: false,
    url: '/get_participants_for_bib_assignment',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race),
  });

  // go to home
  window.location.href = `/home`

}

// AJAX call to update the database with the bib assignements
function sendBibAssignments() {
  $.ajax({
    async: false,
    url: '/update_bib_assignments',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race),
  });
}


// AJAX call to retrieve the current state of the race
function retrieveRaceGroupData() {
  $.ajax({
    async: false,
    url: '/get_participants_for_bib_assignment',
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(race),
    success: function (data) {
        race = data;
        console.log(race);
    }
  });
}


retrieveRaceGroupData();
displayNextPageButton();
