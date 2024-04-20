$(document).ready(function() {
    $('#location-select').on('change', function() {
        let location_id = $(this).val();
        if (location_id) {
            $.ajax({
                url: '/get-courses',
                method: 'POST',
                data: {
                    location_id: location_id
                },
                dataType: 'json',
                success: function(data) {
                    let courses = data;
                    let course_select = $('#course-select');
                    course_select.empty(); // Remove existing options

                    courses.forEach(function(course) {
                        course_select.append(`<option value="${course.id}">${course.name}</option>`);
                    });
                }
            });
        } else {
            $('#course-select').empty();
        }
    });
});
