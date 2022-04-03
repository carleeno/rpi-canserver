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
    updateButtons();
});

sio.on('message', (message) => {
    console.log(message);
    $("<div />").text(message).appendTo("#messages");
    tailScroll();
});

sio.on('stats', (data) => {
    if (data.fps) {
        updateFpsStats(data.fps);
    }
    if (data.system) {
        updateSystemStats(data.system);
    }
});

sio.on('vehicle_stats', (data) => {
    updateVehicleStats(data);
})

function updateFpsStats(fps) {
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

function updateSystemStats(stats) {
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
    updateButtons();
}

function updateVehicleStats(stats) {
    table = document.getElementById('vehicle_stats');
    for (let msg in stats) {
        for (let sig in stats[msg].data) {
            row = document.getElementById(`veh_stat_${msg}_${sig}`);
            if (row == null) {
                row = document.createElement("tr");
                row.id = `veh_stat_${msg}_${sig}`;
                table.tBodies[0].appendChild(row);
            }
            signal = stats[msg].data[sig];
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

function updateButtons() {
    loggingRow0 = document.getElementById('sys_stat_can0 logging');
    loggingRow1 = document.getElementById('sys_stat_can1 logging');
    autologRow0 = document.getElementById('sys_stat_can0 auto-log');
    autologRow1 = document.getElementById('sys_stat_can1 auto-log');

    if (loggingRow0) {
        logging0 = (loggingRow0.getElementsByTagName("TD")[1].innerHTML.includes('true'));
    } else {logging0 = null;}
    if (loggingRow1) {
        logging1 = (loggingRow1.getElementsByTagName("TD")[1].innerHTML.includes('true'));
    } else {logging1 = null;}
    if (autologRow0) {
        autolog0 = (autologRow0.getElementsByTagName("TD")[1].innerHTML.includes('true'));
    } else {autolog0 = null;}
    if (autologRow1) {
        autolog1 = (autologRow1.getElementsByTagName("TD")[1].innerHTML.includes('true'));
    } else {autolog1 = null;}

    logging_buttons = document.getElementById('logging_buttons');
    autolog_buttons = document.getElementById('autolog_buttons');

    if (logging0 & logging1) {
        logging_buttons.innerHTML = '<input type="button" onclick="stopLogging()" value="Stop Logging">';
    } else if (logging0 === false & logging1 === false) {
        logging_buttons.innerHTML = '<input type="button" onclick="startLogging()" value="Start Logging">';
    } else {
        logging_buttons.innerHTML = '<input type="button" onclick="startLogging()" value="Start Logging">';
        logging_buttons.innerHTML += '<input type="button" onclick="stopLogging()" value="Stop Logging">';
    }

    if (autolog0 & autolog1) {
        autolog_buttons.innerHTML = '<input type="button" onclick="autoLoggingOff()" value="Disable Auto Logging">';
        logging_buttons.innerHTML = '';
    } else if (autolog0 === false & autolog1 === false) {
        autolog_buttons.innerHTML = '<input type="button" onclick="autoLoggingOn()" value="Enable Auto Logging">';
    } else {
        autolog_buttons.innerHTML = '<input type="button" onclick="autoLoggingOn()" value="Enable Auto Logging">';
        autolog_buttons.innerHTML += '<input type="button" onclick="autoLoggingOff()" value="Disable Auto Logging">';
    }
}

function startLogging() {
    sio.emit('broadcast_logging_control', 'start');
}

function stopLogging() {
    sio.emit('broadcast_logging_control', 'stop');
}

function autoLoggingOn() {
    sio.emit('broadcast_logging_control', 'auto_on');
}

function autoLoggingOff() {
    sio.emit('broadcast_logging_control', 'auto_off');
}

function tailScroll() {
    var height = $("#messages").get(0).scrollHeight;
    $("#messages").animate({
        scrollTop: height
    }, 500);
}
