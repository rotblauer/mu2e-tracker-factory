import guis.panel.heater.PanelHeater as heatergui
import guis.panel.heater.simple_monitor as monitor
from sys import argv

if __name__ == "__main__":
    if len(argv) > 1:
        monitor.run()
    else:
        heatergui.run()
