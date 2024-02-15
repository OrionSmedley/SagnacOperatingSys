import visa
rm = visa.ResourceManager()
rm.list_resources()
inst = rm.open_resource('GPIB0::20::INSTR')
