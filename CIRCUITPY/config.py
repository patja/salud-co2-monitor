config = {
    'unit_designation' : 'SALUD',
    'sleep_interval' : 300, # seconds to sleep.  Increase to have less frequent updates and longer battery life
    'warn_threshold' : 1000, 
    'alarm_threshold' : 2100,
    'temperature_offset' : 3, # if you care about temp from the sensor.  Probably shouldn't.
    'calibration_ppm' : 425, # important to set this to your location's ambient fresh air CO2 ppm and perform a fresh air calibration
	'elevation' : 93, # elevation in meters above sea level
    'barometric_pressure' : 1014, # this has an impact on humidity readings
    'significant_change' : 25, # only report changes by this amount.  Prevision
    'power_saving_light_level' : 350, # below this light level, sleep longer
    'power_saving_sleep_interval' : 900, # how long to sleep in the dark
    'helpful_url' : 'https://www.prusaprinters.org/print/121265'
}
