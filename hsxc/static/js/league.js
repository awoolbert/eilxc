// route to school page if school box on individual results table is clicked
$('.school').click(function(e) {
  console.log(`school = ${$(this).data('school_id')}`);
  if(!$(e.target).closest('.runner-link').length) {
    lID = $('#league_info').data('league_id');
    sID = $(this).data('school_id');
    var currentURL = (
      window.location.protocol 
      + "//" 
      + window.location.host 
      + window.location.pathname
    );
    var newURL = currentURL.replace(`/${lID}/league`,
                                    `/${sID}/school`);
    window.location.href = newURL;
  }
});

// listen for a change to the year-select element
$('#year-select').change(function() {
  var year = this.value;
  var currentURL = window.location.href;

  const yearPattern = /\/\d{4}\b/;
  const endOfURLPattern = /\/?$/;

  if (yearPattern.test(currentURL)) {
    currentURL = currentURL.replace(yearPattern, '/' + year);
  } else {
    currentURL = currentURL.replace(endOfURLPattern, '/' + year);
  }
  window.location.href = currentURL;
});
