const sio = io({
    transportOptions: {
        polling: {
            extraHeaders: {
                'X-Username': 'browser'
            }
        }
    }
});

sio.on('connect', () => {
    console.log('connected');
    document.getElementById("status").innerHTML = 'Connected';
});

sio.on('connect_error', (e) => {
    console.log(e.message);
    document.getElementById("status").innerHTML = `Error: ${e.message}`;
});

sio.on('disconnect', () => {
    console.log('disconnected');
    document.getElementById("status").innerHTML = 'Disconnected';
    clearTable(document.getElementById('fps_stats'));
    clearTable(document.getElementById('system_stats'));
    clearTable(document.getElementById('vehicle_stats'));
});

sio.on('message', (message) => {
    console.log(message);
    document.getElementById("last_message").innerHTML = message;
});

sio.on('can_frame_batch', (data) => {
    console.log('A frame batch has arrived');
});

sio.on('stats', (data) => {
    if (data.fps) {
        update_fps_stats(data.fps);
    }
    if (data.system) {
        update_system_stats(data.system);
    }
});

sio.on('vehicle_stats', (data) => {
    update_vehicle_stats(data);
})

function update_fps_stats(fps) {
    table = document.getElementById('fps_stats');
    for (let channel in fps) {
        row = document.getElementById(`fps_${channel}`);
        if (row == null) {
            row = document.createElement("tr");
            row.id = `fps_${channel}`;
            table.tBodies[0].appendChild(row);
        }
        row.innerHTML = `<td>${channel}</td><td>${fps[channel]}</td>`;
    }
    sortTable(table);
}

function update_system_stats(stats) {
    table = document.getElementById('system_stats');
    for (let item in stats) {
        row = document.getElementById(`sys_stat_${item}`);
        if (row == null) {
            row = document.createElement("tr");
            row.id = `sys_stat_${item}`;
            table.tBodies[0].appendChild(row);
        }
        row.innerHTML = `<td>${item}</td><td>${stats[item]}</td>`;
    }
    sortTable(table);
}

function update_vehicle_stats(stats) {
    table = document.getElementById('vehicle_stats');
    for (let msg in stats) {
        for (let sig in stats[msg]) {
            row = document.getElementById(`veh_stat_${msg}_${sig}`);
            if (row == null) {
                row = document.createElement("tr");
                row.id = `veh_stat_${msg}_${sig}`;
                table.tBodies[0].appendChild(row);
            }
            row.innerHTML = `<td>${msg}</td><td>${sig}</td><td>${Math.round(stats[msg][sig] * 100) / 100}</td>`;
        }
    }
    sortTable(table);
}

function sortTable(table) {
    var rows, switching, i, x, y, shouldSwitch;
    switching = true;
    while (switching) {
        switching = false;
        rows = table.rows;
        for (i = 1; i < (rows.length - 1); i++) {
            shouldSwitch = false;
            x = rows[i].getElementsByTagName("TD")[0];
            y = rows[i + 1].getElementsByTagName("TD")[0];
            if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) {
                shouldSwitch = true;
                break;
            }
        }
        if (shouldSwitch) {
            rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
            switching = true;
        }
    }
}

function clearTable(table) {
    table.tBodies[0].innerHTML = '';
}

function start_logging() {
    sio.emit('broadcast_start_logging');
}

function stop_logging() {
    sio.emit('broadcast_stop_logging');
}