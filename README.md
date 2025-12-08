# ariya_elm327_wifi
Need to smart charge my Nissan Ariya and need EV battery state in Home Assistant

I use Vgate iCar Pro Wifi (ELM 327 OBD-II) and switch configuration to client mode (STA)

Share this from @dconlon https://github.com/dconlon/icar_obd_wifi
Considering that the vehicle OBD2 port is writable, I don’t want the iCar plugged in permanently broadcasting an open WiFi network.

The 1MB flash version of the LPT230 unfortunately does not have a full web interface but it is sufficient to change WiFi configuration to station mode to have the LPT230 connect to your home WiFi instead of it being an open AP. Whilst connected to the V-LINK WiFi open a web browser to http://192.168.0.10. My device required username "guest” with password “&^)@@)”, another user had success with "admin" and "admin"

Right now ev battery state, and 12v battery from elm327 is working and scan each 10 minutes

To disable power saving on the dongle you can edit disable_powersaving_icar_pro.py and change with you ip address
