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
        let rows = table.find('tr:gt(1)').toArray().sort(
            comparer($(this).index())
        );
        const isAsc = !this.asc; // Store sort order

        $('th').removeClass('asc desc');
        $(this).addClass(isAsc ? 'asc' : 'desc');

        if (!isAsc) rows = rows.reverse();
        for (let i = 0; i < rows.length; i++) table.append(rows[i]);

        this.asc = isAsc;
    });

    // highlight row in races table when hovering over a result in the graph
    var plotlyGraphs = document.querySelectorAll('.js-plotly-plot');
    if (plotlyGraphs.length > 0) {
        var plotlyGraph = plotlyGraphs[0];

        plotlyGraph.on('plotly_hover', function(data){
            var hoverText = data.points[0].hovertext.trim();

            document.querySelectorAll('#races-list tr').forEach(function(row) {
                // Reset the background color for all rows
                row.style.backgroundColor = '';
            
                var timeColumnText = row.cells[5].textContent.trim();
                var raceColumnAnchor = row.cells[1].querySelector('a');
                var raceColumnText = raceColumnAnchor.textContent.trim();

                isRace = hoverText.includes(raceColumnText);
                isTime = hoverText.includes(timeColumnText);
                if (isRace && isTime) {
                    row.style.backgroundColor = 'rgb(250,230,0';
                }
            });
        });
    }    

});
