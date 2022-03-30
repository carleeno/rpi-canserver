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
]

# If you have a pican DUO:
pican_duo = True
