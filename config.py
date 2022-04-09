# Have fun!

dbc_file = "Model3CAN.dbc"

decode_interval = 0.5

# Message names as found in the dbc file:
can_filter = [
    "ID04FGPSLatLong",
    "ID101RCM_inertial1",
    "ID108DIR_torque",
    "ID111RCM_inertial2",
    "ID118DriveSystemStatus",
    "ID129SteeringAngle",
    "ID132HVBattAmpVolt",
    "ID155WheelAngles",
    "ID175WheelSpeed",
    "ID185ESP_brakeTorque",
    "ID186DIF_torque",
    "ID20CVCRIGHT_hvacRequest",
    "ID243VCRIGHT_hvacStatus",
    "ID257DIspeed",
    "ID266RearInverterPower",
    "ID273UI_vehicleControl",
    "ID2E5FrontInverterPower",
    "ID33AUI_rangeSOC",
    "ID3C2VCLEFT_switchStatus",
    "ID528UnixTime",
]

# If you have a pican DUO:
pican_duo = True

# This is used for syncing system time to vehicle time, these values are for Tesla:
vehicle_time_frame_id = "528"
vehicle_time_signal_name = "UnixTimeSeconds528"

# This is used to automatically start/stop logging
vehicle_gear_frame_id = "118"
vehicle_gear_signal_name = "DI_gear"
vehicle_gear_logging_states = ["DI_GEAR_D", "DI_GEAR_N", "DI_GEAR_R"]

# This is used to control auto logging
auto_logging_frame_id = "273"
auto_logging_signal_name = "UI_frontFogSwitch"
auto_logging_on_state = 0
