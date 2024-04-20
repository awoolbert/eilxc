// Function to navigate to a new URL
const navigate = (url) => window.location.href = url;

// Listen for clicks on elements with class "school"
$('.school').click(function() {
    const sID = $('#school_info').data('school_id');
    const oID = $(this).data('school_id');

    // Replace the current school ID in the URL with the clicked element's ID
    const newURL = window.location.pathname.replace(
        `/${sID}/school`, `/${oID}/school`
    );

    navigate(newURL);
});

// Listen for a change to the year-select element
$('#year-select').change(function() {
    const year = this.value;
    let currentURL = window.location.href;

    const yearPattern = /\/\d{4}\b/;
    const endOfURLPattern = /\/?$/;

    currentURL = (
        currentURL.replace(yearPattern.test(currentURL) 
        ? yearPattern 
        : endOfURLPattern, '/' + year)
    );

    navigate(currentURL);
});

// sort roster table when column heading is clicked
$(document).ready(function() {
    const getCellValue = (row, index) => $(row).children('td').eq(index).text();

    const comparer = (index) => (a, b) => {
        const valA = getCellValue(a, index);
        const valB = getCellValue(b, index);
        return (
            ($.isNumeric(valA) && $.isNumeric(valB)) 
            ? valA - valB 
            : valA.toString().localeCompare(valB)
        );
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

