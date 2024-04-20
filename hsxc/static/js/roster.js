$(document).ready(() => {
    $('#runner-form').trigger('reset');

    const runnerData = {};
    const client_data = {
        race_id: $("#team_info").data("race_id"),
        school_id: $("#team_info").data("school_id"),
        gender: $("#team_info").data("gender"),
        team_id: $("#team_info").data("team_id"),
        year: $("#team_info").data("year"),
    };
    console.log(client_data);

    $('.school').click(function() {
        const school_id = $(this).data('school_id');
        console.log(`user clicked school = ${school_id}`);
        const currentURL = `${window.location.protocol}//${window.location.host}${window.location.pathname}`;
        const newURL = currentURL.replace(`/${client_data.team_id}/roster`, `/${school_id}/school/${client_data.year}`);
        window.location.href = newURL;
    });

    $('.add-other-runner-to-roster-btn').click(function() {
        const runner_id = $(this).data('runner_id');
        console.log(`user clicked add runner button for runner = ${runner_id}`);
        const url = new URL(window.location.href);
        url.pathname = url.pathname.replace(
            `/${client_data.team_id}/roster`, 
            `/${client_data.team_id}/${runner_id}/add_runner_to_team`
        );
        window.location.href = url.href;
    });

    $('#gender-select, #year-select').change(function() {
        const changedAttribute = this.id.split('-')[0]; // "gender" or "year"
        var logTxt = `${changedAttribute} has been changed. `;
        logTxt += `Starting changeTeam AJAX route`;
        console.log(logTxt);
        client_data[changedAttribute] = this.value;
        console.log(client_data);
        changeTeam();
    });

    $("#noCreateTeamBtn").click(() => location.reload());

    $("#yesCreateTeamBtn").click(() => {
        console.log('User clicked yes to create new team');
        const url = new URL(window.location.origin);
        url.pathname = '/create_team';
        $.ajax({
            url: url.href,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                school_id: client_data.school_id,
                gender: client_data.gender,
                year: client_data.year
            }),
            success: (data) => {
                console.log(data);
                if (data.status === 'Success') {
                    console.log('Team created successfully');
                    const newURL = new URL(window.location.href);
                    newURL.pathname = newURL.pathname.replace(
                        `/${client_data.team_id}/roster`, 
                        `/${data.team_id}/roster`
                    );
                    window.location.href = newURL.href;
                }
            },
            error: (error) => console.error('Error:', error)
        });
    });

    $('.edit-runner').click(function() {
        const r = $(this).closest('.edit-runner');
        $('#m_first_name').val(r.data('runner_first_name'));
        $('#m_last_name').val(r.data('runner_last_name'));
        $('#m_grad_year').val(r.data('runner_grad_year'));
        $('#m_minutes').val(r.data('runner_minutes'));
        $('#m_seconds').val(r.data('runner_seconds'));
        runnerData['runner_id'] = r.data('runner_id');
    });

    $('#m_update_btn').click(() => {
        runnerData['first_name'] = $('#m_first_name').val();
        runnerData['last_name'] = $('#m_last_name').val();
        runnerData['grad_year'] = $('#m_grad_year').val();
        const minutes = parseInt($('#m_minutes').val());
        const seconds = parseInt($('#m_seconds').val());
        runnerData['seed_time'] = (minutes * 60 + seconds) * 1000;
        console.log('Updating runner...', runnerData);
        updateRunner();
    });

    $('.delete-runner').click(function() {
        const r = $(this).closest('.delete-runner');
        runnerData['first_name'] = r.data('runner_first_name');
        runnerData['last_name'] = r.data('runner_last_name');
        runnerData['grad_year'] = r.data('runner_grad_year');
        runnerData['runner_id'] = r.data('runner_id');
        runnerData['team_id'] = client_data.team_id;
        $('#delete-modal-text').text(
            `Delete ${runnerData['first_name']} ${runnerData['last_name']}, ` +
            `Class of ${runnerData['grad_year']}? Any previous results will ` +
            `remain in the database, but the runner will be removed from the ` +
            `team for all future races.`
        );
    });

    $('#m_confirm_del_btn').click(() => {
        console.log('Deleting runner...', runnerData);
        deleteOrRemoveRunner();
    });

    $('#finished-Editing-Roster-Btn').click(function() {
        const returnUrl = $(this).data('return-url');
        console.log(returnUrl);
        window.location.href = returnUrl;
    });

    const changeTeam = async () => {
        try {
            const response = await $.ajax({
                url: '/change_team',
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(client_data)
            });
            console.log(response);
            if (response.status === 'Found Team') {
                const url = new URL(window.location.origin);
                url.pathname = url.pathname.replace(
                    `/${response.previous_team_id}/roster`, 
                    `/${response.team_id}/roster`
                );
                window.location.href = url.href;
            } else if (response.status === 'No Team') {
                $('#create-team-modal-text').text(response.message);
                $("#createTeamModal").modal('show');
            } else {
                console.log(
                    'Unrecognized response status in changeTeam AJAX route'
                );
            }
        } catch (error) {
            console.error('Error in changeTeam AJAX route', error);
        }
    };

    const updateRunner = async () => {
        try {
            const response = await $.ajax({
                url: '/update_runner',
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(runnerData)
            });
            console.log(response);
            if (response.status === 'success') location.reload();
        } catch (error) {
            console.error('Error in updateRunner AJAX route', error);
        }
    };

    const deleteOrRemoveRunner = async () => {
        try {
            const response = await $.ajax({
                url: '/delete_or_remove_runner',
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(runnerData)
            });
            console.log(response);
            if (response.status === 'success') location.reload();
        } catch (error) {
            console.error('Error in deleteOrRemoveRunner AJAX route', error);
            $('#m_cancel_btn').click();
        }
    };

    const getCellValue = (row, index) => $(row).children('td').eq(index).text();

    const comparer = (index) => (a, b) => {
        const valA = getCellValue(a, index);
        const valB = getCellValue(b, index);
        return $.isNumeric(valA) && $.isNumeric(valB) 
                ? valA - valB 
                : valA.localeCompare(valB);
    };

    $('th.sortable').click(function() {
        const table = $(this).parents('table').eq(0);
        const rows = table.find('tbody tr')
                          .toArray()
                          .sort(comparer($(this).index()));
        const isAsc = !this.asc;
        $(this).toggleClass('asc', isAsc).toggleClass('desc', !isAsc);
        if (!isAsc) rows.reverse();
        table.find('tbody').append(rows);
        this.asc = isAsc;
    });
});
