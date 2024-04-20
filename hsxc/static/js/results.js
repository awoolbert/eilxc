
  // Create the race object and store the race_id
  race = {race_id: document.getElementById("race_info").dataset.race_id};

  // route to school page if school box on individual results table is clicked
  $('.school').click(function(e) {
    console.log(`school = ${$(this).data('school_id')}`);
    if(!$(e.target).closest('.runner-link').length) {
      sID = $(this).data('school_id')
      var currentURL = window.location.protocol + "//" + window.location.host + window.location.pathname;
      var newURL = currentURL.replace(`/${race.race_id}/results`,
                                      `/${sID}/school`);
      window.location.href = newURL;
    }
  });

  // Set race scoring_type when radio button is changed, update database
  // and reload page to update
  $('.form-check-input').change(function() {
    scoring_type = $(this).val();
    race.scoring_type = scoring_type;
    console.log(`Selected ${scoring_type}`);
    updateScoringType();
    location.reload();
  });

  // AJAX call to update the database with the current state of the race
  function updateScoringType() {
    $.ajax({
      async: false,
      url: '/update_scoring_type',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/json',
      data: JSON.stringify(race)
    });
  }

  // function to display an error modal if bib number inputs are invalid
  function invalidEmailModal(title, message) {
    $('#invalidEmailModal').modal('show');
    $('#invalidEmailModalTitle').html(title);
    $('#invalidEmailModalBody').html(message);
  };

  // show email modal when button is pressed
  function showEmailModal() {
    // show modal
    $('#emailResultsModal').modal('show');

    // get the name of the race
    race.race_name = $('#race_info').data('race_name');

    // build title and display in DOM
    title = `Email Race Results for ${race.race_name}`;
    $('#emailResultsModalTitle').html(title);
  };

  // Every time a modal is shown, if it has an autofocus element, focus on it.
  $('.modal').on('shown.bs.modal', function() {
    $(this).find('[autofocus]').focus();
  });

  // Function to check if email is valid
  function isValidEmailAddress(email) {
    // has no @ or has an @ which is too close to the beginning or end
    atIndex = email.indexOf('@')
    if (atIndex <= 0 || atIndex >= email.length - 4) {
      return false;
    }

    // has no dot or has a dot too close to the end
    dotIndex = email.substring(atIndex+1).indexOf('.');
    if (dotIndex == -1 || dotIndex >= email.substring(atIndex+1).length -2) {
      $('#emailResultsModal').modal('hide');
      invalidEmailModal('Error: Invalid email address', 'You have entered an invalid email address.  Please try again.');
      return false;
    }

    // Otherwise email is valid
    return true;

  }


  // Function to send email with bib assignments
  function sendEmail() {
    // get the user input emails
    emails = []
    $('.email-address').each(function(){
      if($(this).val()){
        emails.push($(this).val());
      }
    });

    console.log(`emails array = ${emails}`);

    // Remove blanks from email address list
    for(var i = emails.length -1; i > -1; i--) {
      if(!emails[i]) {
        emails.splice(i, 1);
      }
    }

    recipients = [];
    // check if email(s) valid, warn if not
    for(var i = emails.length -1; i > -1; i--) {
      if(isValidEmailAddress(emails[i])) {
        recipients.push(emails[i]);
      } else {
        $('#emailResultsModal').modal('hide');
        invalidEmailModal(`Error: Invalid email address`, `${emails[i]} is an invalid email address.  Please try again.`);
        return;
      }
    }
    console.log(`email recipients: ${recipients}`);

    // add email address to the emailObject
    var emailObject = {'recipients': recipients,
                       'race_id': race.race_id};

    // send the email address and message content to the server to be mailed
    $.ajax({
      async: true,
      url: '/email_race_results',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/json',
      data: JSON.stringify(emailObject),
    });

    $('#emailResultsModal').modal('hide');
  };
