// Initialize color pickers
const background_picker = new CP($('#background-cp')[0]);
const secondary_picker = new CP($('#secondary-cp')[0]);
const text_picker = new CP($('#text-cp')[0]);

// Cache DOM elements
const $outer_border = $('#outer-border');
const $sample = $('#sample-colors');
const $primary_color = $('#primary_color');
const $secondary_color = $('#secondary_color');
const $text_color = $('#text_color');
const $short_name = $('#short_name');
const $league_id = $('#league_id');

// Event listeners
$short_name.on('blur', function() {
  $sample.text($(this).val());
});

$('#league-id-select').on('change', function() {
  const leagueID = $('option:selected', this).data('league_id');
  console.log(leagueID);
  $league_id.val(leagueID);
});

background_picker.on('change', function(r, g, b, a) {
  const colorValue = this.color(r, g, b, a);
  this.source.value = colorValue;
  $primary_color.val(colorValue);
  $sample.css('background', colorValue);
  $outer_border.css('borderColor', colorValue);
});

secondary_picker.on('change', function(r, g, b, a) {
  const colorValue = this.color(r, g, b, a);
  this.source.value = colorValue;
  $secondary_color.val(colorValue);
  $sample.css('borderColor', colorValue);
});

text_picker.on('change', function(r, g, b, a) {
  const colorValue = this.color(r, g, b, a);
  this.source.value = colorValue;
  $text_color.val(colorValue);
  $sample.css('color', colorValue);
});
