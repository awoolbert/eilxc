// controller for maintaining all raceState data
var dataController = (function() {
  var raceState;  // contains all relevant data on the current race
  var startTime;  // start time (including miliSeconds) of race
  var participants = [];  // array of result objects

  // get race_id and race_status from teh DOM
  const race_id = $("#race_info").data('race_id');
  const race_status = $("#race_info").data('race_status');

  // function to convert time from server to miliseconds
  const getStartingTime = () => {
    var dateFromServer = $("#race_info").data('date');
    var msFromServer = Date.parse(dateFromServer);
    console.log(`Race is currently active, using server starting time of ${dateFromServer}`);
    return msFromServer;
  };

  // if already started set start_time to server time, otherwise null
  if (race_status == 'active') {
    start_time = getStartingTime();
  } else {
    start_time = null;
    console.log('Race has not yet started');
  }

  return {
    // function to update raceState based on the state of the DOM
    getStateData: function(){
      const runnerArr = Array.from(document.querySelectorAll('.runner'));
      const timesArr = Array.from(document.querySelectorAll('.time'));
      participants = [];
      runnerArr.forEach((el, i) => {
        participants.push({
          result_id: parseInt(el.dataset.result_id),
          bib: parseInt(el.dataset.bib),
          place: i + 1,
          runner_id: parseInt(el.dataset.runner_id),
          race_id: parseInt(race_id),
          team_id: parseInt(el.dataset.team_id),
          background_color: el.dataset.background_color,
          color: el.dataset.color,
          team_name: el.dataset.team_name,
          runner_name: el.dataset.runner_name,
        })
      });
      timesArr.forEach((el, i) => {
        participants[i].time = parseInt(el.dataset.time)
      });

      // update the current race state with the data
      raceState = {'race_id':race_id,
                    'race_status':race_status,
                    'start_time':start_time,
                    'participants':participants};

      return raceState;
    },
  };
})();


// controller for updating the DOM
var displayController = (function() {
  var currentClock = "0:00";

  // convert mins and secs to miliSeconds
  const timeToMiliseconds = (mins, secs) => {
    return (mins * 60 + secs) * 1000;
  };

  // Converts a miliseconds time into MM:SS
  const displayTime = (miliSeconds) => {
    var mins = Math.floor( miliSeconds / 60000);
    var secs =  (miliSeconds - mins * 60000) / 1000;
    secs = secs.toFixed(0);
    var secsStr = secs < 10 ? `0${secs}` : secs;
    return `${mins}:${secsStr}`;
  };

  // function to display an error modal if bib number inputs are invalid
  const warningModal = (title, message) => {
    $('#warningModal').modal('show');
    $('#warningModalTitle').html(title);
    $('#warningModalBody').html(message);
  };

  return {
    // Makes the 'runners' table sortable
    startSortable: function(){
      const el = document.getElementById("runners");
      const sortable = Sortable.create(el, {
        handle: '.fa-arrows-alt',
        animation: 150,
        chosenClass: 'blue-white'
      });
    },

    // Sorts the times table in ascending order
    sortTimesTable: function(){
      var table, i, x, y;
      table = document.getElementById("times-table");
      var switching = true;
      // Run loop until no switching is needed
      while (switching) {
          switching = false;
          var rows = table.rows;
          // Loop to go through all rows
          for (i = 1; i < (rows.length - 1); i++) {
              var Switch = false;
              // Fetch 2 elements that need to be compared
              x = rows[i].getElementsByTagName("TD")[0];
              y = rows[i + 1].getElementsByTagName("TD")[0];
              // Check if 2 rows need to be switched
              xTime = parseInt(x.dataset.time);
              yTime = parseInt(y.dataset.time);
              if (xTime > yTime) {
                Switch = true;
                break;
              }
          }
          if (Switch) {
              // Function to switch rows and mark switch as completed
              rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
              switching = true;
          }
      }
    },

    // Iterates over every miliseconds time and converts it for display
    updateTimes: function() {
      const timesArr = Array.from(document.querySelectorAll('.time'));
      timesArr.forEach(el => {
        msTime = parseInt(el.dataset.time);
        el.textContent = displayTime(msTime);
      });
    },

    // Switch formats of the top section of the page once the clock has been started (e.g., change directions, add ticking clock, add adjust clock button, etc.)
    beginTimingFormat: function() {
      var runningClockHTML = `
      <div class="row justify-content-center" id="running-clock-row">
        <div class="col-7 text-right">
          <h4 class="py-2 mr-0 pr-0" id="clock-text">
            Current Time: ${currentClock}
          </h4>
        </div>
        <div class="col text-left py-2 ml-0 pl-0">
          <button class="btn btn-secondary btn-xs" id="edit-time-btn">
            Adjust Time
          </button>
        </div>
      </div>
      <div class="row justify-content-center" id="capture-time-row">
        <div class="col-5 text-center align-self-center">
          <button class="btn btn-block btn-danger" id="capture-time-btn">
            Click Here (or press Enter) to Record a Finish
          </button>
        </div>
      </div>
      `;
      $('#start-clock-cntr').html('');
      $('#running-clock-cntr').html(runningClockHTML);
    },

    updateClock: function(elapsedTime) {
      var clockText = `
        Current Time: ${displayTime(elapsedTime)}
      `;
      $('#clock-text').html(clockText);
        },

    // adds a place and a time to the tables
    addFinishTime: function(finishTime) {
      const timesArr = Array.from(document.querySelectorAll('.time'));
      const runnersArr = Array.from(document.querySelectorAll('.runner'));
      if(runnersArr.length > timesArr.length) {
        place = timesArr.length + 1;
        placeRowHTML = `
        <tr class="placeRow" data-place="${place}">
          <td class="place" data-place="${place}">
            ${place}
          </td>
        </tr>`;

        timeRowHTML = `
        <tr class="timeRow" data-time="${finishTime}">
          <td class="time" data-time="${finishTime}">${displayTime(finishTime)}</td>
          <td class="actions">
            <a class="edit-time" title="Edit" data-toggle="tooltip">
              <i class="material-icons">&#xE254;</i>
            </a>
            <a class="delete-time" title="Delete" data-toggle="tooltip">
              <i class="material-icons">&#xE872;</i>
            </a>
          </td>
        </tr>`;

        places = document.getElementById('places');
        times = document.getElementById('times');
        places.insertAdjacentHTML('beforeend', placeRowHTML);
        times.insertAdjacentHTML('beforeend', timeRowHTML);
      }
    },

    // deletes and redraws tables (this is needed because addFinishTime seems
    // to add rows that are slightly misaligned between the three tables, and
    // that misalignment compounds as many entries are made)
    updateTables: function(raceState) {
      console.log('Updating the tables');

      // get the table bodies
      places = document.getElementById('places');
      runners = document.getElementById('runners');
      times = document.getElementById('times');

      // clear the existing table bodies
      places.innerHTML = '';
      runners.innerHTML = '';
      times.innerHTML = '';

      // loop through participants creating new rows for each
      raceState.participants.forEach((p) => {
        var placeRowHTML = '';
        var runnerRowHTML = '';
        var timeRowHTML = '';

        // if time exists, create HTML for a place row
        if("time" in p) {
          placeRowHTML = `
          <tr class="placeRow" data-place="${p.place}">
            <td class="place" data-place="${p.place}">
              ${p.place}
            </td>
          </tr>`;
        }

        // create HTML for the runner row
        runnerRowHTML = `
          <tr class="runner"
              data-result_id="${p.result_id}"
              data-runner_id="${p.runner_id}"
              data-bib="${p.bib}"
              data-team_id="${p.team_id}"
              data-background_color="${p.background_color}"
              data-color="${p.color}"
              data-team_name="${p.team_name}"
              data-runner_name="${p.runner_name}">
            <td style="background-color:${p.background_color};  color:${p.color};">
              ${p.team_name}
            </td>
            <td>
              ${p.runner_name}
            </td>
            ${p.bib ? 
              `<td class="text-center">
                ${p.bib}
              </td>` : ''}
            </td>
            <td class="text-center">
              <span class="fas fa-arrows-alt"></span>
            </td>
          </tr>
        `;

        // if time exists, create HTML for a time row
        if("time" in p) {
          timeRowHTML = `
          <tr class="timeRow" data-time="${p.time}">
            <td class="time" data-time="${p.time}">${displayTime(p.time)}</td>
            <td class="actions">
              <a class="edit-time" title="Edit" data-toggle="tooltip">
                <i class="material-icons">&#xE254;</i>
              </a>
              <a class="delete-time" title="Delete" data-toggle="tooltip">
                <i class="material-icons">&#xE872;</i>
              </a>
            </td>
          </tr>`;
        }

        // insert new rows into DOM
        places.insertAdjacentHTML('beforeend', placeRowHTML);
        runners.insertAdjacentHTML('beforeend', runnerRowHTML)
        times.insertAdjacentHTML('beforeend', timeRowHTML);
      });


    },

    showEditTimeModal: function(raceClock) {
      if (raceClock == 1) {
        $('#editTimeModalTitle').text('Enter Official Time and Press Sync');
        $('#syncBtn').text('Sync');
        $('#editTimeModal').modal('show');
      } else {
        $('#editTimeModalTitle').text('Enter New Time and Press Update');
        $('#syncBtn').text('Update');
        $('#editTimeModal').modal('show');
      }
    },

    getTimeFromModal: function() {
      var mins = parseInt($('#minutes').val());
      var secs = parseInt($('#seconds').val());

      // warn if entries are not valid
      if (isNaN(mins) || isNaN(secs) || mins < 0 || secs < 0 || secs > 59) {
        warningModal('Entry Error', 'Please enter two valid numbers and retry');
        return 0;
      }

      // Clear the values and hide the modal
      $('#minutes').val('');
      $('#seconds').val('');
      $('#editTimeModal').modal('hide');

      // Convert the user input to miliseconds time
      return timeToMiliseconds(mins, secs);

    },

    changeFinishTime: function(miliseconds) {
      // change the values for the selected timeRow
      timeRowToEdit = $('#timeRowToEdit');
      timeRowToEdit.attr('data-time',miliseconds.toString());

      // change the values for the td in the selected timeRow
      timeRowToEdit.find('.time').attr('data-time',miliseconds.toString());
      timeRowToEdit.find('.time').text(displayTime(miliseconds));

      // remove the id to 'unselect' this row
      timeRowToEdit.removeAttr('id');

      // Clear the values and hide the modal
      $('#minutes').val('');
      $('#seconds').val('');
      $('#editTimeModal').modal('hide');
    },

    removeFinishTime: function(timeIndex) {
      $('.timeRow').eq(timeIndex).remove();
      $('.placeRow').eq(timeIndex).remove();
      $('.placeRow').each(function(index, el) {
        $(el).data('place', index + 1);
        $(el).html(`<td>${index + 1}</td>`);
      });
      $('#deleteTimeModal').modal('hide');
    },

    getRowIndex: function(row) {
      $('.timeRow').each( function(index, el) {
        if ($(el).data('time') == row.data('time')) {
          rowIndex = index;
        }
      });
      $('#deleteTimeModal').modal('show');
      return rowIndex;
    },

    removeFinishButton: function() {
      $('#finish-ctr').html('');
    },

    replaceFinishButton: function() {
      html = `
      <div class="row justify-content-center">
        <button class="btn btn-primary btn-lg" id="finish-btn">
          Race Finished
        </button>
      </div>
      `;
      $('#finish-ctr').html(html);
    },

  }
})();


// main controller
var appController = (function(dataCtrl, dispCtrl) {
  var startTime, clockStarted, lastClick, raceState, status;
  var rowIndex;
  var raceClock, timeRowToEdit;
  var lastClick = false;
  var openRequests = 0;

  const startEventListeners = () => {
    // Start the clock
    $(document).on('click','#start-btn',function(){
      dispCtrl.beginTimingFormat();
            startClock();
      updateRaceState();
    });

    // Record a time
    $(document).on('click','#capture-time-btn',function(){
      // Ensure this is a valid click (i.e., not an echo) and capture time
      if(Date.now() - lastClick > 20) {
        lastClick = Date.now();
        captureTime();
      }
    });

    // Adjust the clock to sync with the official time
    $(document).on('click','#edit-time-btn',function(){
      raceClock = 1; // we are editing the overall race time
      dispCtrl.showEditTimeModal(raceClock);
    });

    // Adjust the clock to sync with the official time
    $(document).on('click','.edit-time',function(){
      raceClock = 0; // we are editing an individual finish time
      dispCtrl.showEditTimeModal(raceClock);
      // identify this timeRow as the one being edited
      $(this).closest('.timeRow').attr('id', 'timeRowToEdit');
    });

    // Adjust the clock to sync with the official time
    $(document).on('click','#syncBtn',function(){
      // get the time from the user input
      enteredTime = dispCtrl.getTimeFromModal();

      // break if entry is invalid
      if (!enteredTime) {return;}

      // determine if updating raceClock or individual finish time
      if (raceClock == 1) {
        // Calculate the difference between entered time and current time
        var currentTime = Date.now() - startTime;
        var timeAdjustment = enteredTime - currentTime;

        // Adjust the start time and update the database
        startTime -= timeAdjustment;

      } else {
        // Update the DOM with the new finish time
        dispCtrl.changeFinishTime(enteredTime);

        // sort the times to ensure finishes are in order
        dispCtrl.sortTimesTable();
      }

      // update the database
      updateRaceState();
    });

    // Every time a modal is shown, if it has an autofocus element, focus on it.
    $('.modal').on('shown.bs.modal', function() {
      $(this).find('[autofocus]').focus();
    });

    // Record a time using the enter key
    document.addEventListener('keypress', function(e){
      if(Date.now() - lastClick > 20) {
        lastClick = Date.now();
        if (e.keyCode === 13 || e.which === 13) {
          if(clockStarted) {
            captureTime();
          }
        }
      }
    });

    // Whenever a sorting has occured, update the state and send to server (potentially store locally)
    document.addEventListener('dragend', () => {
      updateRaceState();
    });

    // Delete the time and corresponding place when the delete icon is selected
    // and the action is confirmed with a modal
    $(document).on('click', '.delete-time', function(e) {
      // Get the time associated with this delete button
      rowIndex = dispCtrl.getRowIndex($(this).closest('.timeRow'));
    });
    $(document).on('click', '#deleteTimeBtn', function() {
      dispCtrl.removeFinishTime(rowIndex);
      updateRaceState();
    });

    // show the finish race model when button pressed
    $(document).on('click', '#finish-btn', function() {
      // show confirm modal
      $('#finishRaceModal').modal('show');
    });

    // when finish is confirmed, update database and show results
    $(document).on('click', '#finishAndScoreBtn', function() {
      // set race status to complete
      status = 'complete';
      // update the database
      updateRaceStateSynchronous();
      // redirect to results
      window.location.href = `/${raceState.race_id}/results`
    });
  };

  // Record the finish time, add it to the DOM and update the database
  const captureTime = () => {
    var finishTime = (Date.now() - startTime);
    dispCtrl.addFinishTime(finishTime);
    dispCtrl.sortTimesTable();
    updateRaceState();
    dispCtrl.updateTables(raceState);
  };

  // When start button is pressed (or when page is loaded in 'active' status)
  // set the start_time and start clock ticking
  var startClock = function(start_time=false) {
        clockStarted = true;
    if(start_time) {
      startTime = start_time;
    } else {
      startTime = Date.now();
      status = 'active';
    }
        function time() {
            var elapsedTime = Date.now() - startTime;
            dispCtrl.updateClock(elapsedTime);
        }
        setInterval(time, 10);
    };

  // Updates the race state based on the most recent times and order and then
  // sends it to the server for storage in the event the page is refreshed
  const updateRaceState = () => {
    // Get the race state from the data controller
    raceState = dataCtrl.getStateData();
    raceState.start_time = startTime;
    raceState.race_status = status ? status : raceState.race_status;
    console.log(raceState);

    // keep track of open requests. if they exceed 1, remove finish button
    openRequests++;
    if (openRequests > 1) {
      dispCtrl.removeFinishButton();
    }

    // send raceState to server to update database
    $.ajax({
      async: true,
      url: '/update_race_state',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/json',
      data: JSON.stringify(raceState),
      complete: function(data) {
        // decrement open requests as they are returned. restore the finish
        // button once none remain open
        openRequests--;
        if (openRequests == 0) {
          dispCtrl.replaceFinishButton();
        }
    }
    });
  };

  const updateRaceStateSynchronous = () => {
    // Get the race state from the data controller
    raceState = dataCtrl.getStateData();
    raceState.start_time = startTime;
    raceState.race_status = status ? status : raceState.race_status;
    console.log(raceState);

    // Do final update with status set to complete
    $.ajax({
      async: false,
      url: '/update_race_state',
      type: 'POST',
      dataType: 'json',
      contentType: 'application/json',
      data: JSON.stringify(raceState),
    });
  };

  return {
    init: function() {
      raceState = dataCtrl.getStateData();
      console.log(raceState);
      if(raceState.start_time) {
        dispCtrl.beginTimingFormat();
        startClock(raceState.start_time);
      }
      startEventListeners();
      dispCtrl.startSortable();
      dispCtrl.updateTimes();
    }
  }
})(dataController, displayController)

appController.init();

