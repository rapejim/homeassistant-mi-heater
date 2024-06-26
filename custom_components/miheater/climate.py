"""
    Support for Xiaomi wifi-enabled home heaters via miio.
    author: sunfang1cn@gmail.com
    modifier: ee02217
    Tested environment: HASS 0.118.5
"""
import logging

import voluptuous as vol
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (DOMAIN,
                                                    ClimateEntityFeature,
                                                    HVACMode)
from homeassistant.const import (ATTR_TEMPERATURE, CONF_HOST, CONF_NAME,
                                 CONF_TOKEN, UnitOfTemperature)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from miio import Device, DeviceException

_LOGGER = logging.getLogger(__name__)

CONF_MODEL = 'model'
DEVICE_MODEL = ""
MAX_TEMP = 28
MIN_TEMP = 18
MIN_TEMP_ZB1 = 16
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default='Xiaomi Heater'): cv.string,
    vol.Optional(CONF_MODEL, default=None): vol.In(
    ['zhimi.heater.mc2',
     'zhimi.heater.mc2a',
     'zhimi.heater.zb1',
     'zhimi.heater.za2',
     'zhimi.heater.za1', None]),
})
REQUIREMENTS = ['python-miio>=0.5.0']
SERVICE_SET_ROOM_TEMP = 'miheater_set_room_temperature'
SET_ROOM_TEMP_SCHEMA = vol.Schema({
    vol.Optional('temperature'): cv.positive_int
})
SUPPORT_FLAGS = (ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON)



def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Xiaomi heaters."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    model = config.get(CONF_MODEL)

    _LOGGER.debug("Initializing Xiaomi heaters with host %s (token %s...)", host, token[:5])

    devices = []
    unique_id = None

    try:
        device = Device(host, token)
        device_info = device.info()
        
        if model is None:
            
            model = device_info.model
            DEVICE_MODEL = model

        unique_id = f"{model}-{device_info.mac_address}"
        _LOGGER.debug("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)
        miHeater = MiHeater(device, name, model, unique_id, hass)
        devices.append(miHeater)
        add_devices(devices)


        async def set_room_temp(service):
            """Set room temp."""
            
            if DEVICE_MODEL == "zhimi.heater.mc2" or DEVICE_MODEL == "zhimi.heater.mc2a":
                aux = device.raw_command('get_properties', [{"siid":2,"piid":5,"did":None}])
            elif DEVICE_MODEL == "zhimi.heater.zb1" or DEVICE_MODEL == "zhimi.heater.za2":
                aux = device.raw_command('get_properties', [{"siid":2,"piid":6}])
            elif DEVICE_MODEL == "zhimi.heater.za1":
                aux = device.raw_command('get_properties', [{"siid":3,"piid":1}])
            else  :  
                _LOGGER.exception("Unsupported model: %s", DEVICE_MODEL)

            temperature=aux[0]["value"]
            await miHeater.async_set_temperature(temperature)

        hass.services._async_register(DOMAIN, SERVICE_SET_ROOM_TEMP,
                                     set_room_temp, schema=SET_ROOM_TEMP_SCHEMA)
    except DeviceException:
        _LOGGER.exception("Fail to setup Xiaomi heater")
        raise PlatformNotReady



class MiHeater(ClimateEntity):
    """Representation of a MiHeater device."""

    def __init__(self, device, name, model, unique_id, _hass):
        """Initialize the heater."""
        self._device = device
        self._name = name
        self._model = model
        self._state = None
        self._attr_unique_id = unique_id
        self.entity_id = generate_entity_id('climate.{}', unique_id, hass=_hass)
        self.getAttrData()
        self._enable_turn_on_off_backwards_compatibility = False # For avoid warning logs

    if DEVICE_MODEL == "zhimi.heater.zb1" or DEVICE_MODEL == "zhimi.heater.za2" or DEVICE_MODEL == "zhimi.heater.za1" :
        @property
        def current_humidity(self):
            """Return the current humidity."""
            return self._state['humidity']

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._state['current_temperature']

    @property
    def device(self):
        """Return the model of the device."""
        return self._model

    @property
    def extra_state_attributes(self):
        return self._state
        
    @property
    def hvac_mode(self):
        return HVACMode.HEAT if self._state['power'] else HVACMode.OFF

    @property
    def hvac_modes(self):
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def is_on(self):
        """Return true if heater is on."""
        return self._state['power']

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._model == "zhimi.heater.zb1" or self._model == "zhimi.heater.za2" or self._model == "zhimi.heater.za1" :
            return MIN_TEMP_ZB1 
        else:
            return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._state['target_temperature']

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return UnitOfTemperature.CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def getAttrData(self):

        try:
            data = {}
               
            if self._model == "zhimi.heater.mc2" or self._model == "zhimi.heater.mc2a":
                power=self._device.raw_command('get_properties', [{"siid":2,"piid":1,"did":None}])
                target_temperature=self._device.raw_command('get_properties', [{"siid":2,"piid":5,"did":None}])
                current_temperature=self._device.raw_command('get_properties', [{"siid":4,"piid":7,"did":None}])
            elif self._model == "zhimi.heater.zb1" or self._model == "zhimi.heater.za2" :
                power=self._device.raw_command('get_properties', [{"siid":2,"piid":2}])
                target_temperature=self._device.raw_command('get_properties', [{"siid":2,"piid":6}])
                current_temperature=self._device.raw_command('get_properties', [{"siid":5,"piid":8}])
                humidity=self._device.raw_command('get_properties', [{"siid":5,"piid":7}])
                data['humidity'] = humidity[0]["value"]
            elif self._model == "zhimi.heater.za1" :
                power=self._device.raw_command('get_properties', [{"siid":2,"piid":1}])
                target_temperature=self._device.raw_command('get_properties', [{"siid":2,"piid":2}])
                current_temperature=self._device.raw_command('get_properties', [{"siid":3,"piid":1}])
                humidity=self._device.raw_command('get_properties', [{"siid":3,"piid":2}])
                data['humidity'] = humidity[0]["value"]
            else:  
                _LOGGER.exception("Unsupported model: %s", self._model)

            data['power'] = power[0]["value"]
            data['target_temperature'] = target_temperature[0]["value"]
            data['current_temperature'] = current_temperature[0]["value"]
            self._state = data
        except DeviceException:
            _LOGGER.exception("Fail to get_prop from Xiaomi heater")
            self._state = None
            raise PlatformNotReady

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Setting temperature: %s", int(temperature))
        if temperature is None:
            _LOGGER.error("Wrong temperature: %s", temperature)
            return
        
        if self._model == "zhimi.heater.mc2" or self._model == "zhimi.heater.mc2a":              
            self._device.raw_command('set_properties',[{"value":int(temperature),"siid":2,"piid":5, "did":None}])
        elif self._model == "zhimi.heater.zb1" or self._model == "zhimi.heater.za2" :
            self._device.raw_command('set_properties',[{"value":int(temperature),"siid":2,"piid":6}])
        elif self._model == "zhimi.heater.za1" :
            self._device.raw_command('set_properties',[{"value":int(temperature),"siid":2,"piid":2}])
        else:  
            _LOGGER.exception("Unsupported model: %s", self._model)

    async def async_turn_on(self):
        """Turn Mill unit on."""
        if self._model == "zhimi.heater.mc2" or self._model == "zhimi.heater.mc2a":              
            self._device.raw_command('set_properties',[{"value":True,"siid":2,"piid":1, "did":None}])
        elif self._model == "zhimi.heater.zb1" or self._model == "zhimi.heater.za2" :
            self._device.raw_command('set_properties',[{"value":True,"siid":2,"piid":2}])
        elif self._model == "zhimi.heater.za1" :
            self._device.raw_command('set_properties',[{"value":True,"siid":2,"piid":1}])
        else:  
            _LOGGER.exception("Unsupported model: %s", self._model)        
        

    async def async_turn_off(self):
        """Turn Mill unit off."""
        if self._model == "zhimi.heater.mc2" or self._model == "zhimi.heater.mc2a":              
            self._device.raw_command('set_properties',[{"value":False,"siid":2,"piid":1, "did":None}])
        elif self._model == "zhimi.heater.zb1" or self._model == "zhimi.heater.za2" :
            self._device.raw_command('set_properties',[{"value":False,"siid":2,"piid":2}])
        elif self._model == "zhimi.heater.za1" :
            self._device.raw_command('set_properties',[{"value":False,"siid":2,"piid":1}])
        else:  
            _LOGGER.exception("Unsupported model: %s", self._model)    
        
    async def async_update(self):
        """Retrieve latest state."""
        self.getAttrData()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        if hvac_mode  == HVACMode.HEAT or hvac_mode  == HVACMode.COOL:
            await self.async_turn_on()
        elif hvac_mode  == HVACMode.OFF:
            await self.async_turn_off()
        else:
            _LOGGER.error("Unrecognized operation mode: %s", hvac_mode)
