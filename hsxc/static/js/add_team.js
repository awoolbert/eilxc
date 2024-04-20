$(document).ready(function() {
  $('#gender-select').on('change', function() {
    var school_id = $(this).data('school_id');
    var race_id = $(this).data('race_id');
    var selected_option = $(this).find('option:selected');
    var gender_code = selected_option.data('gender_code');

    var url = `/${school_id}/${race_id}/${gender_code}/create_team`;
      window.location.href = url;
  });
});
  