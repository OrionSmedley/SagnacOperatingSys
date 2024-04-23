import pararameters as p

settings = pararametrs()

settings.lockin.out1.voltage = 1
settings.lockin.out2.freq = 3



A = []
D =[]
B = []


obj = F (A, D, B, settings)


for parameterSet in obj.get_next_parameter_sets
Run_experiemt( obj.next_parame_set() )
