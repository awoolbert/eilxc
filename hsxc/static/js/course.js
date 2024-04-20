$(document).ready(function() {

    // route to school page if school box on individual results table is clicked
    $('.school').click(function(e) {
        school_id = $(this).data('school_id')
        course_id = $('#course-id').data('course_id')
        console.log(`user clicked school = ${school_id}`);
        console.log(`course_id = ${course_id}`);

        var currentURL = (
            window.location.protocol 
            + "//" 
            + window.location.host 
            + window.location.pathname
        );
        var newURL = currentURL.replace(
            `/${course_id}/course`,
            `/${school_id}/school`
        );
        window.location.href = newURL;
    });


    $('.runner-count').click(function() {
      var course_id = $(this).data('course_id');
      $('#runner-diffs-modal-' + course_id).modal('show');
    });

    const getCellValue = (row, index) => $(row).children('td').eq(index).text();

    const parseValue = (value) => {
        // Trim whitespace from the value
        const trimmedValue = value.trim();
    
        // Check for percentage values with a '+' or '-' prefix
        if (trimmedValue.endsWith('%')) {
            // Remove the '%' and parse it as a number
            return parseFloat(trimmedValue.slice(0, -1));
        } else if ((trimmedValue[0] === '+' || trimmedValue[0] === '-') && $.isNumeric(trimmedValue.substring(1, trimmedValue.length - 1))) {
            // Parse it as a number if it has a '+' or '-' prefix
            return parseFloat(trimmedValue);
        } else if (trimmedValue.includes(':') && /^\d+:\d+$/.test(trimmedValue)) {
            // If the value is in the format of minutes:seconds, convert it to seconds
            const [minutes, seconds] = trimmedValue.split(':').map(Number);
            return minutes * 60 + seconds;
        } else if ($.isNumeric(trimmedValue)) {
            // If it's a numeric string, parse it as a number
            return parseFloat(trimmedValue);
        }
        // Otherwise, return the value as a string
        return trimmedValue.toLowerCase();
    };
    
    const comparer = (index) => (a, b) => {
        const valA = parseValue(getCellValue(a, index));
        const valB = parseValue(getCellValue(b, index));
        if (typeof valA === 'number' && typeof valB === 'number') {
            return valA - valB;
        } else if (typeof valA === 'string' && typeof valB === 'string') {
            return valA.localeCompare(valB);
        } else {
            // Handle the case where one is a string and the other is a number
            return typeof valA === 'string' ? 1 : -1;
        }
    };
    
    $('th.sortable').click(function() {
        const table = $(this).parents('table').eq(0);
        let rows = table.find('tr:gt(0)').toArray().sort(comparer($(this).index()));
        const isAsc = !this.asc; // Store sort order
    
        $('th').removeClass('asc desc');
        $(this).addClass(isAsc ? 'asc' : 'desc');
    
        if (!isAsc) rows = rows.reverse();
        for (let i = 0; i < rows.length; i++) table.append(rows[i]);
    
        this.asc = isAsc;
    });
        
});
