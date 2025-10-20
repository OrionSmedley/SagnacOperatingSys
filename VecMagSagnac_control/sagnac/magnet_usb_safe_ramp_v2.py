from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np, math
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa
from .instruments.AMI420 import AMI420
from sagnac.instruments import APS100
import atto_device.CRYO2100 as cr

class Magnet:
    ATOL = 1e-3
    Tthresh = 4.4
    def __init__(self, x_axis_tilt=91.4, y_axis_tilt=89.3, phi_offset=0.0):
        self.device_x = APS100("COM4")
        self.device_2 = APS100("COM5")
        # device 2 channel 1 is Z
        # device 2 channel 2 is Y

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet
        self._field_difference_cutoff = 0 #1e-5 # 0.1 G

    

        self._field_mag_lim = 9.5 # set to 1? bootleg version is kG, previous auttodry gui was T

        self._B_sign = 1

        self.atto = cr("192.168.1.1")
        self.atto.connect()
        # self.Bx_set, self.By_set, self.Bz_set = self.get_field_cartesian()
        # self.B_set, self.phi_set, self.theta_set = self.get_field_polar()
        # --- geometry / offsets ---
        self.x_axis_tilt = float(x_axis_tilt)
        self.y_axis_tilt = float(y_axis_tilt)
        self._phi_offset = float(phi_offset)

        # --- sample-frame ground truth (spherical) + caches ---
        self._B_samp = 0.0
        self._phi_samp = 0.0
        self._theta_samp = 0.0
        self._phi_samp_cache = 0.0
        self._theta_samp_cache = 0.0

        # --- lab spherical (derived; kept in sync) ---
        self._B = 0.0
        self._phi_lab = 0.0
        self._theta_lab = 0.0

        # misc from your original
        self._field_difference_cutoff = 0
        self._field_mag_lim = 9.5
        self._B_sign = 1
        self._Toverheat = 4.55
        self._Tcooling = (self._Toverheat - 0.40)
        self._Tflag = (self._Toverheat - 0.2)
        self._flag = 1

        # initialize lab from sample
        self._sync_lab_from_sample()

    # ---------------- math helpers ----------------
    @staticmethod
    def _norm_deg(x):
        x = x % 360.0
        return 0.0 if x >= 360.0 - 1e-12 else x

    @staticmethod
    def sph2cart(B, phi, theta):
        phi_r, th_r = math.radians(phi), math.radians(theta)
        return np.array([B*math.sin(th_r)*math.cos(phi_r),
                         B*math.sin(th_r)*math.sin(phi_r),
                         B*math.cos(th_r)], dtype=float)

    @staticmethod
    def cart2sph(Bx, By, Bz, prev_phi=None, prev_theta=None, eps=1e-12):
        Bperp = math.hypot(Bx, By)
        B = math.hypot(Bperp, Bz)
        if B < eps:
            # |B| ~ 0: return cached angles
            phi = 0.0 if prev_phi is None else (prev_phi % 360.0)
            if phi >= 360.0 - 1e-12: phi = 0.0
            theta = 0.0 if prev_theta is None else float(prev_theta)
            return 0.0, phi, theta

        if Bperp < eps * B:
            # at the pole: keep previous phi (or 0)
            phi = 0.0 if prev_phi is None else (prev_phi % 360.0)
            if phi >= 360.0 - 1e-12: phi = 0.0
        else:
            phi = math.degrees(math.atan2(By, Bx)) % 360.0
            if phi >= 360.0 - 1e-12: phi = 0.0

        ct = max(-1.0, min(1.0, Bz / B))
        theta = math.degrees(math.acos(ct))
        return B, phi, theta

    # ---------------- frame geometry ----------------
    @property
    def R(self):
        # sample axes in lab coordinates (NO phi_offset here)
        x_dir = self.sph2cart(1.0, 0.0,  self.x_axis_tilt)
        y_dir = self.sph2cart(1.0, 90.0, self.y_axis_tilt)

        z_hat = np.cross(x_dir, y_dir); z_hat /= np.linalg.norm(z_hat)
        x_plane = x_dir / np.linalg.norm(x_dir)
        y_plane = np.cross(z_hat, x_plane); y_plane /= np.linalg.norm(y_plane)

        # columns are sample axes expressed in lab coords
        return np.column_stack((x_plane, y_plane, z_hat))

    # ---------------- lab vector internal ----------------
    def _lab_vec(self):
        return self.sph2cart(self._B, self._phi_lab, self._theta_lab)

    def _update_lab(self, Bx, By, Bz):
        # robust spherical from cartesian (lab)
        self._B, self._phi_lab, self._theta_lab = self.cart2sph(
            Bx, By, Bz, prev_phi=self._phi_lab, prev_theta=self._theta_lab
        )

    # ---------------- sync: sample <-> lab ----------------
    def _sync_lab_from_sample(self):
        # encode: add offset when mapping sample -> lab
        phi_eff = self._norm_deg(self._phi_samp + self._phi_offset)
        lab = self.R @ self.sph2cart(self._B_samp, phi_eff, self._theta_samp)
        self._update_lab(*lab)

    def _sync_sample_from_lab(self):
        # decode: subtract offset when mapping lab -> sample
        bx, by, bz = self.R.T @ self._lab_vec()
        prev_phi_eff = self._norm_deg(self._phi_samp + self._phi_offset)
        B, phi_eff, theta = self.cart2sph(
            bx, by, bz, prev_phi=prev_phi_eff, prev_theta=self._theta_samp
        )
        self._B_samp = B
        self._phi_samp = self._norm_deg(phi_eff - self._phi_offset)
        self._theta_samp = theta
        # keep caches current
        self._phi_samp_cache = self._phi_samp
        self._theta_samp_cache = self._theta_samp

    # ---------------- sample spherical (GROUND TRUTH) ----------------
    @property
    def B_samp(self):
        return self._B_samp, self._phi_samp, self._theta_samp

    @B_samp.setter
    def B_samp(self, val):
        B, phi, theta = val
        self._B_samp = float(B)
        self._phi_samp = self._norm_deg(float(phi))
        self._theta_samp = float(theta)
        self._phi_samp_cache = self._phi_samp
        self._theta_samp_cache = self._theta_samp
        self._sync_lab_from_sample()

    @property
    def B(self): return self._B_samp
    @B.setter
    def B(self, v):
        self._B_samp = float(v)
        self._sync_lab_from_sample()

    @property
    def phi(self): return self._phi_samp
    @phi.setter
    def phi(self, v):
        self._phi_samp = self._norm_deg(float(v))
        self._phi_samp_cache = self._phi_samp
        self._sync_lab_from_sample()

    @property
    def theta(self): return self._theta_samp
    @theta.setter
    def theta(self, v):
        self._theta_samp = float(v)
        self._theta_samp_cache = self._theta_samp
        self._sync_lab_from_sample()

    # ---------------- sample cartesian (derived from sample spherical) ----------------
    def _samp_cart_now(self):
        return self.sph2cart(self._B_samp, self._phi_samp, self._theta_samp)

    @property
    def Bx(self): return self._samp_cart_now()[0]
    @Bx.setter
    def Bx(self, v):
        s = self._samp_cart_now().copy(); s[0] = float(v)
        Bn, phin, thetan = self.cart2sph(*s,
            prev_phi=self._phi_samp_cache, prev_theta=self._theta_samp_cache)
        self.B_samp = (Bn, phin, thetan)

    @property
    def By(self): return self._samp_cart_now()[1]
    @By.setter
    def By(self, v):
        s = self._samp_cart_now().copy(); s[1] = float(v)
        Bn, phin, thetan = self.cart2sph(*s,
            prev_phi=self._phi_samp_cache, prev_theta=self._theta_samp_cache)
        self.B_samp = (Bn, phin, thetan)

    @property
    def Bz(self): return self._samp_cart_now()[2]
    @Bz.setter
    def Bz(self, v):
        s = self._samp_cart_now().copy(); s[2] = float(v)
        Bn, phin, thetan = self.cart2sph(*s,
            prev_phi=self._phi_samp_cache, prev_theta=self._theta_samp_cache)
        self.B_samp = (Bn, phin, thetan)

    # ---------------- lab spherical (derived; setters back-solve sample) ----------------
    @property
    def B_lab(self): return self._B
    @B_lab.setter
    def B_lab(self, v):
        self._B = float(v)
        self._sync_sample_from_lab()

    @property
    def phi_lab(self): return self._phi_lab
    @phi_lab.setter
    def phi_lab(self, v):
        self._phi_lab = self._norm_deg(float(v))
        self._sync_sample_from_lab()

    @property
    def theta_lab(self): return self._theta_lab
    @theta_lab.setter
    def theta_lab(self, v):
        self._theta_lab = float(v)
        self._sync_sample_from_lab()

    # ---------------- lab cartesian (derived; setters back-solve sample) ----------------
    @property
    def Bx_lab(self): return self._lab_vec()[0]
    @Bx_lab.setter
    def Bx_lab(self, v):
        _, y, z = self._lab_vec()
        self._update_lab(float(v), y, z)
        self._sync_sample_from_lab()

    @property
    def By_lab(self): return self._lab_vec()[1]
    @By_lab.setter
    def By_lab(self, v):
        x, _, z = self._lab_vec()
        self._update_lab(x, float(v), z)
        self._sync_sample_from_lab()

    @property
    def Bz_lab(self): return self._lab_vec()[2]
    @Bz_lab.setter
    def Bz_lab(self, v):
        x, y, _ = self._lab_vec()
        self._update_lab(x, y, float(v))
        self._sync_sample_from_lab()

    # ---------------- phi_offset (re-encode lab; sample stays unchanged) ----------------
    @property
    def phi_offset(self): return self._phi_offset
    @phi_offset.setter
    def phi_offset(self, val):
        self._phi_offset = float(val)
        self._sync_lab_from_sample()


    #######################################
    ############### Old Hardware connections #################

    def connect(self):
        if self.device_x.connection and self.device_x.connection.is_open:
            self.device_x.disconnect()
        if self.device_2.connection and self.device_2.connection.is_open:
            self.device_2.disconnect()
        self.device_x.connect()
        self.device_x.write_command("REMOTE")
        self.device_2.connect()
        self.device_2.write_command("REMOTE")
        Bx, By, Bz = self.get_field_cartesian()
        print( "conecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        print(f"The field tilts are X = {self.x_axis_tilt} and Y = {self.y_axis_tilt} deg")
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            self.device_x.disconnect()
            self.device_2.disconnect()
            print( "Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
            raise ValueError("Bmag vector is larger than 0.9 T! Don't touch anything else! call Kelly")
        
        self.Bx, self.By, self.Bz = self.get_field_cartesian()
        
    def setSafe_wait(self, junk = 0):
        temp = self.atto.condenser.getTemperature()
        if temp > self.Tthresh:
            # atto.disconnect() 
            print( f"yikes, resevoir at {temp}C > max {self.Tthresh}")
            self.shutdown()
            raise RuntimeError(f"shut down bc resevoir at {temp}C > max {self.Tthresh}")

        tic = time()
        Bx_init, By_init, Bz_init = self.get_field_cartesian()
        # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
        if not np.abs(self.Bz_lab) > np.abs(Bz_init): 
            # print("entering if")
            while not self.check_field_cartesian(Bx_init, By_init, self.Bz_lab, 10*self.ATOL):
                # print("waiting for z to ramp down")
                sleep(0.1)
                self.set_field_cartesian(Bx_init,By_init,self.Bz_lab)
                sleep(0.1)
                print(f"waiting for z to ramp down {time()-tic}")

        while not self.check_field_cartesian(self.Bx_lab, self.By_lab, self.Bz_lab, self.ATOL):
            sleep(0.1)
            self.set_field_cartesian(self.Bx_lab, self.By_lab, self.Bz_lab)
            sleep(0.1)
            print(f"waiting for mag for {time()-tic}")


    # The methods below are unchanged from the OG 

    def set_field_cartesian(self, Bx, By, Bz):
        """
        Sets the field using a cartesian basis
        """
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        
        # self.device.magnet.setHSetPoint3D(Bz, By, Bx)
        self.device_x.set_field(Bx)
        self.device_2.set_channel(1) # z 
        self.device_2.set_field(Bz)
        self.device_2.set_channel(2) # y
        self.device_2.set_field(By)
        
    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        self.device_2.set_channel(1) # z
        Bz = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        Bx = self.device_x.get_field()
        return Bx, By, Bz

    def check_field_cartesian(self, Bx_set, By_set, Bz_set, ATOL):
        """Checks the current field value to make sure it is within absolute tolerance of setpoint """
        # Bx_current = self.device.magnet.getH(2)
        # By_current = self.device.magnet.getH(1)
        # Bz_current = self.device.magnet.getH(0)
        self.device_2.set_channel(1) # z
        Bz_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bx_current = self.device_x.get_field()

        if np.isclose(Bx_set,Bx_current, atol=ATOL) and np.isclose(By_set,By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current, atol=ATOL):
            # log.info("Field is not close to the setpoint")
            log.info("field is close to the setpoint")
            return True
        else:
            log.info(f"{Bx_current}, {By_current}, {Bz_current}")
            return False



# magnet = Magnet(1, 0, 0)

# print("Initial B:", magnet.B)
# print("Initial Phi:", magnet.phi)
# print("Initial Theta:", magnet.theta)

# magnet.phi = 90
# print("After setting phi to 90°:", magnet.get_cartesian())

# magnet.theta = 45
# print("After setting theta to 45°:", magnet.get_cartesian())

# magnet.B = 2
# print("After setting magnitude to 2:", magnet.get_cartesian())
