# Have fun!


can0_bus = "ChassisBus"
can0_dbc = "Model3CAN.dbc"
# Message names as found in the dbc file:
can0_filter = [
    "ID04FGPSLatLong",
    "ID101RCM_inertial1",
    "ID111RCM_inertial2",
    "ID155WheelAngles",
    "ID175WheelSpeed",
    "ID185ESP_brakeTorque",
]
can0_filter_exact_match = True

# If you have a pican DUO:
pican_duo = True
can1_bus = "VehicleBus"
can1_dbc = "Model3CAN.dbc"
# Message names as found in the dbc file:
can1_filter = [
    "ID186DIF_torque",
    "ID108DIR_torque",
    "ID2E5FrontInverterPower",
    "ID266RearInverterPower",
    "ID118DriveSystemStatus",
    "ID129SteeringAngle",
    "ID257DIspeed",
    "ID132HVBattAmpVolt",
    "ID33AUI_rangeSOC",
    "ID243VCRIGHT_hvacStatus",
    "ID20CVCRIGHT_hvacRequest",
    "ID273UI_vehicleControl",
    "ID3C2VCLEFT_switchStatus",
]
can1_filter_exact_match = True
