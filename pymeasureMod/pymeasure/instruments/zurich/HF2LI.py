#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2017 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

from time import sleep
import numpy as np
from zhinst.ziPython import ziDAQServer


class HF2LI(ziDAQServer):
    """This is the class for the Zurich HF2LI lockin amplifier"""
    def __init__(self, port, API_level, dev_num):
        super().__init__('localhost', port, API_level)
        self.dev = '/dev' + str(dev_num) + '/'
        self.dev_num = dev_num

    # Signal Inputs; Our model has 2; 0-indexed
    def get_range(self, sig):
        return self.getDouble(self.dev + 'sigins/' + str(sig) + '/range')
    def set_range(self, sig, x):
        self.setDouble(self.dev + 'sigins/' + str(sig) + '/range', x)

    def get_ac_coupling(self, sig):
        return self.getInt(self.dev + 'sigins/' + str(sig) + '/ac')
    def set_ac_coupling(self, sig, x):
        self.setInt(self.dev + 'sigins/' + str(sig) + '/ac', int(x))

    def get_imp50(self, sig):
        return self.getInt(self.dev + 'sigins/' + str(sig) + '/imp50')
    def set_imp50(self, sig, x):
        self.setInt(self.dev + 'sigins/' + str(sig) + '/imp50', int(x))

    def get_differential_mode(self, sig):
        return self.getInt(self.dev + 'sigins/' + str(sig) + '/diff')
    def set_differential_mode(self, sig, x):
        self.setInt(self.dev + 'sigins/'+ str(sig) + '/diff', int(x))

    # Oscillators; Our model has 6; 0-indexed
    def get_osc_freq(self, osc_num):
        return self.getDouble(self.dev + 'oscs/' + str(osc_num) + '/freq')
    def set_osc_freq(self, osc_num, x):
        self.setDouble(self.dev + 'oscs/'+ str(osc_num) + '/freq', x)

    # Demodulators
    def get_osc_select(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/oscselect')
    def set_osc_select(self, demod_num, osc_num):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/oscselect', int(osc_num))

    def get_harmonic(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/harmonic')
    def set_harmonic(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/harmonic', int(x))

    def get_phase(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/phaseshift')
    def set_phase(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/phaseshift', x)

    def get_input(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/adcselect')
    def set_input(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/adcselect', x)

    def get_filter_order(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/order')
    def set_filter_order(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/order', x)

    def get_tc(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/timeconstant')
    def set_tc(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/timeconstant', x)

    def get_sinc(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/sinc')
    def set_sinc(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/sinc', x)

    def get_enable_demod(self, demod_num):
        return self.getInt(self.dev + 'demods/' + str(demod_num) + '/enable')
    def set_enable_demod(self, demod_num, x):
        self.setInt(self.dev + 'demods/'+ str(demod_num) + '/enable', x)

    def get_xferRate(self, demod_num):
        return self.getDouble(self.dev + 'demods/' + str(demod_num) + '/rate')
    def set_xferRate(self, demod_num, x):
        self.setDouble(self.dev + 'demods/'+ str(demod_num) + '/rate', x)

    # Output Amplitudes; a linear comb of up to 8 Sine outputs
    def get_vout(self, out_num, osc_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/amplitudes/' + str(osc_num))
    def set_vout(self, out_num, osc_num, x):
        self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/amplitudes/' + str(osc_num), x)

    def get_enable_output(self, out_num, osc_num):
        return self.getInt(self.dev + 'sigouts/' + str(out_num) + '/enables/' + str(osc_num))
    def set_enable_output(self, out_num, osc_num, x):
        self.setInt(self.dev + 'sigouts/'+ str(out_num) + '/enables/' + str(osc_num), x)

    # Signal outputs
    def get_sigon(self, out_num):
        return self.getInt(self.dev + 'sigouts/' + str(out_num) + '/on')
    def set_sigon(self, out_num, x):
        self.setInt(self.dev + 'sigouts/'+ str(out_num) + '/on', x)

    def get_sigadd(self, out_num):
        return self.getInt(self.dev + 'sigouts/' + str(out_num) + '/add')
    def set_sigadd(self, out_num, x):
        self.setInt(self.dev + 'sigouts/'+ str(out_num) + '/add', x)

    def get_outrange(self, out_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/range')
    def set_outrange(self, out_num, x):
        self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/range', x)

    def get_offset(self, out_num):
        return self.getDouble(self.dev + 'sigouts/' + str(out_num) + '/offset')
    def set_offset(self, out_num, x):
        self.setDouble(self.dev + 'sigouts/'+ str(out_num) + '/offset', x)


    # Data Collection
    def sample(self, demod_num):
        return self.getSample(self.dev + 'demods/' + str(demod_num) + '/sample')

    def sub(self, demod_num):
        self.subscribe(self.dev + 'demods/' + str(demod_num) + '/sample')

    def poll_and_unpack(self, poll_time, poll_timeout, demod_nums, data_keys, ratio=True, average = True):
        if not isinstance(demod_nums, list):
            demod_nums = [demod_nums]
        if not isinstance(data_keys, list):
            data_keys = [data_keys]
        dat = self.poll(poll_time,poll_timeout)['dev' + str(self.dev_num)]['demods']
        return_dict = {d:{} for d in demod_nums}
        for d in demod_nums:
            for k in data_keys:
                while True:
                    try:
                        if average:
                            return_dict[d][k] = float(np.mean(dat[str(d)]['sample'][k]))
                        else:
                            return_dict[d][k] = dat[str(d)]['sample'][k]
                    except:
                        sleep(poll_time)
                        dat = self.poll(poll_time,poll_timeout)['dev' + str(self.dev_num)]['demods']
                    else:
                        break
        if ratio and average:
            return_dict['ratio'] = float(np.mean(dat['0']['sample']['x']/dat['1']['sample']['y']))
        if ratio and not average:
            return_dict['ratio'] = dat['0']['sample']['x']/dat['1']['sample']['y']
        return return_dict



    def shutdown(self):
        log.info("Shutting down Zurich Lock-in")
        self.set_sigon(0,0)
        self.set_sigon(1,0)
        log.info("Done shutting down Lock-in")
        # self.isShutdown = True
