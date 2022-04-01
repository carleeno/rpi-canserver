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
        if (stats[item].unit) { 
            rowHTML = `<td>${item}</td><td>${stats[item].value} ${stats[item].unit}</td>`;
        } else {
            rowHTML = `<td>${item}</td><td>${stats[item].value}</td>`
        }
        row.innerHTML = rowHTML;
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
            signal = stats[msg][sig];
            svalue = Math.round(signal.value*100000000)/100000000;
            sname = signal.name;
            sunit = signal.unit;
            if (sname) {
                rowHTML = `<td>${msg}</td><td>${sig}</td><td>${sname}</td>`;
            } else if (sunit) {
                rowHTML = `<td>${msg}</td><td>${sig}</td><td>${svalue} ${sunit}</td>`;
            } else {
                rowHTML = `<td>${msg}</td><td>${sig}</td><td>${svalue}</td>`;
            }
            
            row.innerHTML = rowHTML;
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
    sio.emit('broadcast_logging_control', 'start');
}

function stop_logging() {
    sio.emit('broadcast_logging_control', 'stop');
}

function auto_logging_on() {
    sio.emit('broadcast_logging_control', 'auto_on');
}

function auto_logging_off() {
    sio.emit('broadcast_logging_control', 'auto_off');
}
