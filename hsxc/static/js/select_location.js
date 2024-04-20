$(document).ready(function() {
    // Attach a change event listener to the select element
    $('#location-select').on('change', function() {
        // Get the data-location_id attribute value of the selected option
        const locationId = $(this).find('option:selected').data('location_id');

        // Check if locationId is "add"
        if (locationId === "add") {
            window.location.href = '/add_location';
        } else if (locationId) {
            // Construct the URL and redirect for other location ids
            window.location.href = `/add_course/${locationId}`;
        }
    });
});
