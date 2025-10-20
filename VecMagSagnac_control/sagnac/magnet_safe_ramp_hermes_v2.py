from time import sleep, time
import logging
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

import numpy as np, math
import pandas as pd
from pymeasure.instruments.validators import truncated_range
from pymeasure.instruments import Instrument
import pyvisa

from aparatus.sagnac4 import TM620

class MagPowSup:
    
    def __init__(self, IPAddress):
        self.resourcestr = f"TCPIP0::{IPAddress}::4444::SOCKET"
        self.instrument = None
    
    def connect(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(self.resourcestr)
        self.instrument.read_termination = '\r\n'
        self.instrument.write_termination = '\r\n'
        
    def disconnect(self):
        if self.instrument:
            self.instrument.close()
    
    def query(self, command):
        return self.instrument.query(command)

    def write(self, command):
        self.instrument.write(command)

    def set_channel(self, channel):
        self.write(f'CHAN {int(channel)}')
        res = self.query('CHAN?')
        return res

    def get_field(self):
        # print("checking field")
        value = np.nan
        while np.isnan(value):
            try:
                res = self.query('IMAG?')
                value = float(res.replace('kG', ''))
                return value
            except:
                value =  np.nan
                sleep(1)
                
    def pause_field(self):
        response = self.query('SWEEP?')
        # print(f"Response is {response}")
        if response != 'Standby':
            while response != 'Pause':
                self.write('SWEEP PAUSE')
                sleep(0.05)
                response = self.query('SWEEP?')
                print(f"Mag ramp now set to {response}")    
        
    def temp_check(self, Tthresh):
        Tmag = TM620.Tmag
        if Tmag > float(Tthresh):
            sleep(2)
            print(f"Waiting for magnet to cool from {Tmag} to {np.round(Tthresh,3)}")
            return False
        else:
            return True        
            
    def set_field(self, field):
        current_field = self.get_field()
        sleep(0.1)
        if field == 0:
            if self.is_ramping() == 'Standby':
                pass
            else:
                self.zero_field()
        else:
            if field - current_field > 0.001:
                self.write(f'ULIM {field}')
                sleep(0.1)
                self.write('SWEEP UP')
            elif field - current_field < -0.001:
                self.write(f'LLIM {field}')
                sleep(0.1)
                self.write('SWEEP DOWN')
            else:
                pass

    def check_field(self, set_field, tol = 0.001):
        current_field = self.get_field()
        if abs(set_field - current_field) > tol:
            return False
        else:
            return True    

    def is_ramping(self):
        check = self.query('SWEEP?')
        # print(f"Ramping check is {check}")
        return check

    def zero_field(self):
        self.write('SWEEP ZERO')

# class Magnet:
#     ATOL = 1e-3
#     def __init__(self, x_axis_tilt=90, y_axis_tilt=90, phi_offset=0.0):
#         self.device_2 = MagPowSup('169.254.62.188')
#         self.device_z = MagPowSup('169.254.62.187')
#         # device 2 channel 1 is X
#         # device 2 channel 2 is Y
        
#         self.x_axis_tilt = x_axis_tilt
#         self.y_axis_tilt = y_axis_tilt
#         self._phi_offset = float(phi_offset)
#         self._phi_samp_cache = 0.0
#         self._B, self._phi_lab, self._theta_lab = 0.0, 0.0, 0.0
#         self._B_samp = 0.0
#         self._phi_samp = 0.0
#         self._theta_samp = 0.0
#         self._theta_samp_cache = 0.0


#         # limit such that below this field change the magnet does not actually change field,
#         # to limit commands sent to the magnet
#         self._field_difference_cutoff = 0 #1e-5 # 0.1 G

#         self._field_mag_lim = 9.5 # set to 1? bootleg version is kG, previous auttodry gui was T

#         self._B_sign = 1 
        
        
#         self._Toverheat = 4.55
#         self._Tcooling = (self._Toverheat - 0.40)
#         self._Tflag = (self._Toverheat - 0.2)
#         self._flag = 1

#     @staticmethod
#     def sph2cart(B, phi, theta):
#         phi, theta = math.radians(phi), math.radians(theta)
#         return np.array([B*math.sin(theta)*math.cos(phi),
#                          B*math.sin(theta)*math.sin(phi),
#                          B*math.cos(theta)])

#     @staticmethod
#     def cart2sph(Bx, By, Bz, prev_phi=None, eps=1e-12):
#         B = math.sqrt(Bx*Bx + By*By + Bz*Bz)
#         if B < eps:
#             # Magnitude essentially zero: pick canonical angles
#             return 0.0, (0.0 if prev_phi is None else prev_phi % 360), 0.0

#         Bperp = math.sqrt(Bx*Bx + By*By)
#         if Bperp < eps * B:
#             # At/near the pole: phi is undefined -> keep previous or 0
#             phi = 0.0 if prev_phi is None else (prev_phi % 360.0)
#             if phi >= 360.0 - 1e-12:
#                 phi = 0.0
#         else:
#             phi = math.degrees(math.atan2(By, Bx))
#             phi = (phi % 360.0)
#             if phi >= 360.0 - 1e-12:  # clamp 359.999999999 -> 0
#                 phi = 0.0

#         # Guard acos domain with clamp
#         ct = max(-1.0, min(1.0, Bz / B))
#         theta = math.degrees(math.acos(ct))
#         return B, phi, theta
    
#     def _BphiTheta_now(self):
#         bx, by, bz = self.R.T @ self._lab_vec()
#         return self.cart2sph(bx, by, bz, prev_phi=self._phi_samp_cache)

#     # @property
#     # def R(self):
#     #     # Step 1: Get tilted vectors in lab frame
#     #     x_dir = self.sph2cart(1.0, 0.0,  self.x_axis_tilt)   # tilted lab X
#     #     y_dir = self.sph2cart(1.0, 90.0, self.y_axis_tilt)   # tilted lab Y

#     #     # Step 2: Sample Z = normalized cross
#     #     z_hat = np.cross(x_dir, y_dir)
#     #     z_hat /= np.linalg.norm(z_hat)

#     #     # Step 3: Gram–Schmidt in the plane to get orthonormal X,Y
#     #     x_plane = x_dir / np.linalg.norm(x_dir)
#     #     x_plane /= np.linalg.norm(x_plane)

#     #     y_plane = np.cross(z_hat, x_plane)
#     #     y_plane /= np.linalg.norm(y_plane)

#     #     # Step 4: In-plane rotation by phi_offset about z_hat
#     #     phi = math.radians(self._phi_offset)
#     #     x_hat = x_plane * math.cos(phi) - y_plane * math.sin(phi)
#     #     y_hat = x_plane * math.sin(phi) + y_plane * math.cos(phi)

#     #     # Step 5: Rotation matrix (columns are sample axes in lab coords)
#     #     return np.column_stack((x_hat, y_hat, z_hat))
#     @property
#     def R(self):
#         x_dir = self.sph2cart(1.0, 0.0,  self.x_axis_tilt)
#         y_dir = self.sph2cart(1.0, 90.0, self.y_axis_tilt)

#         z_hat = np.cross(x_dir, y_dir); z_hat /= np.linalg.norm(z_hat)
#         x_plane = x_dir / np.linalg.norm(x_dir)
#         y_plane = np.cross(z_hat, x_plane); y_plane /= np.linalg.norm(y_plane)

#         # NO phi_offset rotation here
#         return np.column_stack((x_plane, y_plane, z_hat))


#     def _lab_vec(self): return self.sph2cart(self._B, self._phi_lab, self._theta_lab)
#     def _update_lab(self, Bx, By, Bz):
#         # Preserve lab phi near the poles to avoid arbitrary jumps
#         self._B, self._phi_lab, self._theta_lab = self.cart2sph(
#             Bx, By, Bz, prev_phi=self._phi_lab
#         )    


#     # lab‑frame spherical
#     @property
#     def B_lab(self): return self._B
#     @B_lab.setter
#     def B_lab(self, v): self._B = v
    
#     @property
#     def phi_lab(self): return self._phi_lab
#     @phi_lab.setter
#     def phi_lab(self, v): self._phi_lab = v % 360
    
#     @property
#     def theta_lab(self): return self._theta_lab
#     @theta_lab.setter
#     def theta_lab(self, v): self._theta_lab = v

#     # lab‑frame Cartesian
#     @property
#     def Bx_lab(self): return self._lab_vec()[0]
#     @Bx_lab.setter
#     def Bx_lab(self, v): _, y, z = self._lab_vec(); self._update_lab(v, y, z)
    
#     @property
#     def By_lab(self): return self._lab_vec()[1]
#     @By_lab.setter
#     def By_lab(self, v): x, _, z = self._lab_vec(); self._update_lab(x, v, z)
    
#     @property
#     def Bz_lab(self): return self._lab_vec()[2]
#     @Bz_lab.setter
#     def Bz_lab(self, v): x, y, _ = self._lab_vec(); self._update_lab(x, y, v)

#     # # sample‑frame Cartesian
#     # @property
#     # def Bx(self): return (self.R.T @ self._lab_vec())[0]
#     # @Bx.setter
#     # def Bx(self, v): s = self.R.T @ self._lab_vec(); s[0]=v; self._update_lab(*(self.R @ s))
    
#     # @property
#     # def By(self): return (self.R.T @ self._lab_vec())[1]
#     # @By.setter
#     # def By(self, v): s = self.R.T @ self._lab_vec(); s[1]=v; self._update_lab(*(self.R @ s))
    
#     # @property
#     # def Bz(self): return (self.R.T @ self._lab_vec())[2]
#     # @Bz.setter
#     # def Bz(self, v): s = self.R.T @ self._lab_vec(); s[2]=v; self._update_lab(*(self.R @ s))
    
#     # sample-frame Cartesian  (consistent with sample spherical; ignores phi_offset)
#     def _samp_cart_now(self):
#         B, phi, theta = self.B_samp      # offset-free sample angles
#         return self.sph2cart(B, phi, theta)

#     @property
#     def Bx(self): return self._samp_cart_now()[0]
#     @Bx.setter
#     def Bx(self, v):
#         s = self._samp_cart_now().copy()
#         s[0] = float(v)
#         Bn, phin, thetan = self.cart2sph(*s, prev_phi=self._phi_samp_cache)
#         self.B_samp = (Bn, phin, thetan)

#     @property
#     def By(self): return self._samp_cart_now()[1]
#     @By.setter
#     def By(self, v):
#         s = self._samp_cart_now().copy()
#         s[1] = float(v)
#         Bn, phin, thetan = self.cart2sph(*s, prev_phi=self._phi_samp_cache)
#         self.B_samp = (Bn, phin, thetan)

#     @property
#     def Bz(self): return self._samp_cart_now()[2]
#     @Bz.setter
#     def Bz(self, v):
#         s = self._samp_cart_now().copy()
#         s[2] = float(v)
#         Bn, phin, thetan = self.cart2sph(*s, prev_phi=self._phi_samp_cache)
#         self.B_samp = (Bn, phin, thetan)

#     # sample‑frame spherical (B, phi, theta)
#     # @property
#     # def B_samp(self):
#     #     bx, by, bz = self.R.T @ self._lab_vec()
#     #     B, phi, theta = self.cart2sph(bx, by, bz, prev_phi=self._phi_samp_cache)
#     #     self._phi_samp_cache = phi
#     #     return B, phi, theta
    
#     @property
#     def B_samp(self):
#         bx, by, bz = self.R.T @ self._lab_vec()
#         # use prev_phi in the *effective* frame for pole stability
#         prev_phi_eff = (self._phi_samp_cache + self._phi_offset) % 360.0
#         B, phi_eff, theta = self.cart2sph(bx, by, bz, prev_phi=prev_phi_eff)
#         phi = (phi_eff - self._phi_offset) % 360.0     # <-- subtract offset for sample report
#         self._phi_samp_cache = phi
#         return B, phi, theta
    
#     # @B_samp.setter
#     # def B_samp(self, val):
#     #     lab = self.R @ self.sph2cart(*val)
#     #     self._update_lab(*lab)
    
#     @B_samp.setter
#     def B_samp(self, val):
#         B, phi, theta = val
#         phi_eff = (phi + self._phi_offset) % 360.0     # <-- add offset to encode for lab
#         lab = self.R @ self.sph2cart(B, phi_eff, theta)
#         self._update_lab(*lab)
        
#     @property
#     def B(self): return self.B_samp[0]
#     @B.setter
#     def B(self, val):
#         _, phi0, theta0 = self._BphiTheta_now()
#         self.B_samp = (float(val), phi0, theta0)
        
#     @property
#     def phi(self): return self.B_samp[1]
#     @phi.setter
#     def phi(self, val):
#         B0, _, theta0 = self._BphiTheta_now()   # side-effect free
#         self._phi_samp_cache = float(val) % 360.0
#         self.B_samp = (B0, self._phi_samp_cache, theta0)
    
#     @property
#     def theta(self): return self.B_samp[2]
#     @theta.setter
#     def theta(self, val):
#         B0, _, _ = self._BphiTheta_now()        # side-effect free
#         self.B_samp = (B0, self._phi_samp_cache, float(val))
        
#     @property
#     def phi_offset(self):
#         return self._phi_offset

#     @phi_offset.setter
#     def phi_offset(self, val):
#         # Keep the *same* sample-frame (B,phi,theta), but recompute lab vector with new R
#         B0, phi0, theta0 = self.B_samp  # computed with *old* R
#         self._phi_offset = float(val)
#         self.B_samp = (B0, phi0, theta0)  # reapply via *new* R

class Magnet:
    ATOL = 1e-3

    def __init__(self, x_axis_tilt=90, y_axis_tilt=90, phi_offset=0.0):
        # --- hardware (leave as-is if you have these drivers) ---
        self.device_2 = MagPowSup('169.254.62.188')  # ch1=X, ch2=Y (your mapping)
        self.device_z = MagPowSup('169.254.62.187')

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
        self.device_z.disconnect()
        self.device_2.disconnect()

        if self.device_z.instrument is None:
            self.device_z.connect()
        if self.device_2.instrument is None:
            self.device_2.connect()   
        
        self.device_z.write("REMOTE")
        self.device_2.write("REMOTE")
        
        Bx, By, Bz = self.get_field_cartesian()
        
        self.quench_check()
        self.voltage_check()
        
        print("Connecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        print(f"X and Y axis tilts are: {self.x_axis_tilt}°, {self.y_axis_tilt}°")
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim:
            self.device_z.disconnect()
            self.device_2.disconnect()
            print("Bmag vector is larger than 0.95 T! Don't touch anything else! call Kelly")
            raise ValueError("Bmag vector is larger than 0.95 T! Don't touch anything else! call Kelly")
        
        self.Bx, self.By, self.Bz = self.get_field_cartesian()

    def voltage_check(self):
        zvolt = self.device_z.query("VOUT?")

        self.device_2.set_channel(1) # x
        xvolt = self.device_2.query("VOUT?")
        
        self.device_2.set_channel(2) # y
        yvolt = self.device_2.query("VOUT?")
        print(xvolt, yvolt, zvolt)
        
    def quench_check(self):
        zquench = self.device_z.query("*STB?")
        binary_form = format(ord(zquench), '08b')
        # print(binary_form[-3])
        if (binary_form[-3] == '1') :
            print("Quench in Z")
            
        self.device_2.set_channel(1) # x
        xquench = self.device_2.query("*STB?")
        binary_form = format(ord(xquench), '08b')
        # print(binary_form[-3])
        if (binary_form[-3] == '1') :
            print("Quench in X")
        
        self.device_2.set_channel(2) # y
        yquench = self.device_2.query("*STB?")
        binary_form = format(ord(yquench), '08b')
        # print(binary_form[-3])
        if (binary_form[-3] == '1') :
            print("Quench in Y")
        
        
    def setSafe_wait(self, junk = 0):
        # print("1")
        tic = time()
        # print("2")
        Bx_init, By_init, Bz_init = self.get_field_cartesian()
        # print("3")
        # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
        mag_safe = self.check_temps()
        # print("4")
        # print(f"Mag safe is: {mag_safe}")
        if mag_safe != None:
            if not np.abs(self.Bz_lab) > np.abs(Bz_init): 
                # print("entering if")
                while not self.check_field_cartesian(Bx_init, By_init, self.Bz_lab, 10*self.ATOL):
                    print("waiting for z to ramp down")
                    mag_safe = self.check_temps()
                    # print(f"Mag safe 3 is {mag_safe}")
                    sleep(0.1)
                    if mag_safe == True:
                        self.set_field_cartesian(Bx_init,By_init,self.Bz_lab)
                        sleep(0.1)
                        print(f"waiting for z to ramp down {time()-tic}")
            while not self.check_field_cartesian(self.Bx_lab, self.By_lab, self.Bz_lab, self.ATOL):
                mag_safe = self.check_temps()
                # print(f"Mag safe 4 is {mag_safe}")
                sleep(0.1)
                if mag_safe == True:
                    self.set_field_cartesian(self.Bx_lab, self.By_lab, self.Bz_lab)
                    sleep(0.1)
                    print(f"waiting for mag for {time()-tic}")
                    
    def test_ramp(self, junk = 0):
        print(f"Setting field to (Bx, By, Bz) =<{self.Bx_lab},{self.By_lab},{self.Bz_lab}>")
        print(f"Setting field to (B, φ, θ) = <{self.B_lab},{self.phi_lab},{self.theta_lab}>")
        sleep(5)


    def set_field_cartesian(self, Bx, By, Bz):
        """
        Sets the field using a cartesian basis
        """
        if np.sqrt(Bx*Bx + By*By + Bz*Bz) > self._field_mag_lim: #np.sqrt returns positive square root
            log.error("A large field of %g was requested"%np.sqrt(Bx*Bx + By*By + Bz*Bz))
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        
        # self.device.magnet.setHSetPoint3D(Bz, By, Bx)
        self.device_z.set_field(Bz)
        self.device_2.set_channel(1) # x 
        self.device_2.set_field(Bx)
        self.device_2.set_channel(2) # y
        self.device_2.set_field(By)
        
    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        self.device_2.set_channel(1) # x
        Bx = self.device_2.get_field()
        # print(Bx)
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        # print(By)
        Bz = self.device_z.get_field()
        # print(Bz)
        return Bx, By, Bz

    def check_field_cartesian(self, Bx_set, By_set, Bz_set, ATOL):
        """Checks the current field value to make sure it is within absolute tolerance of setpoint """
        # Bx_current = self.device.magnet.getH(2)
        # By_current = self.device.magnet.getH(1)
        # Bz_current = self.device.magnet.getH(0)
        self.device_2.set_channel(1) # x
        Bx_current = self.device_2.get_field()
        self.device_2.set_channel(2) # y
        By_current = self.device_2.get_field()
        Bz_current = self.device_z.get_field()
        
        print(f"Bx, By, Bz is currently {Bx_current},{By_current},{Bz_current}")

        if np.isclose(Bx_set, Bx_current,atol=ATOL) and np.isclose(By_set, By_current,atol=ATOL) and np.isclose(Bz_set, Bz_current,atol=ATOL):
            # log.info("Field is not close to the setpoint")
            print("Field is close to the setpoint (I owe my existence to Ethan Berg, all hail o7)")
            return True
        else:
            # print(f"{Bx_current}, {By_current}, {Bz_current}")
            # print("I don't think the field is close enough")
            return False

    def pause_all(self):
        
        self.device_2.set_channel(1) # x check
        self.device_2.pause_field()
        self.device_z.pause_field()
        self.device_2.set_channel(2) # y check
        self.device_2.pause_field()        
        
        check1 = self.device_z.is_ramping()
        # print(f"Check1 is {check1}")
        if check1 != "Pause" or check1 != "Standby":
            self.device_z.pause_field()
        
        self.device_2.set_channel(1) # x check
        check2 = self.device_2.is_ramping()
        # print(f"Check2 is {check2}")
        if check2 == "Pause" or check2 != "Standby":
            self.device_2.pause_field()
            
        self.device_2.set_channel(2) # y check
        check3 = self.device_2.is_ramping()
        # print(f"Check3 is {check3}")
        if check3 != "Pause" or check3 != "Standby":
            self.device_2.pause_field()
        
    def check_temps(self):
        """Checks the Magnet Thermometer Temperature to know if the ramp rate needs to be paused"""
        bigcheck = self.device_z.temp_check(self._Toverheat)
        shield = TM620.Tshield
        
        if bigcheck == True and shield <= 55:
            bigcheck == True
        else: 
            bigcheck == False
        
        # print(f"bigcheck 1 is {bigcheck}")
            
        if bigcheck != False:
            secondcheck = self.device_z.temp_check((self._Tflag))
            cooldowncountdown = time()        
            if secondcheck == False or self._flag == 2: 
                self._flag = 2
                print(f"Overheat flag is up")
                while self._flag != 1:
                    if (time() - cooldowncountdown) < 1800:
                        # print(f"Threshold is {self._Tcooling}")
                        # print(f"Flag is up")
                        zcheck = self.device_z.temp_check(self._Tcooling)
                        
                        # print(f"Zcheck 1 is {zcheck}")
                        
                        if zcheck == True:
                            self._flag = 1
                            print(f"FLAG IS NOW RESET after {time() - cooldowncountdown}")
                            return True
                        
                        else:
                            self.pause_all()
                            # check1 = self.device_z.is_ramping()
                            # print(f"Check1 is {check1}")
                            # if check1 != "Pause" or check1 != "Standby":
                            #     self.device_z.pause_field()
                            
                            # self.device_2.set_channel(1) # x check
                            # check2 = self.device_2.is_ramping()
                            # print(f"Check2 is {check2}")
                            # if check2 == "Pause" or check2 != "Standby":
                            #     self.device_2.pause_field()
                                
                            # self.device_2.set_channel(2) # y check
                            # check3 = self.device_2.is_ramping()
                            # print(f"Check3 is {check3}")
                            # if check3 != "Pause" or check3 != "Standby":
                            #     self.device_2.pause_field()

                            zcheck = self.device_z.temp_check(self._Tcooling)

                    else:
                        timeout = pd.Timestamp.now()
                        print(f"Magnet unable to cool down. Ramping down all magnets and ending the scan. {timeout}")
                        self.shutdown()
                    
            elif secondcheck == True:
                if self._flag == 1:
                    return True 
                
        else:
            timeout = pd.Timestamp.now() 
            if shield > 55:
                print(f"Shield is too hot, stop this, call Ethan ASAP before ramping magnet or Kelly {timeout}")
                self.shutdown()
            else:
                print(f"Magnet is too hot, stop this, call Ethan ASAP before ramping magnet or Kelly {timeout}")
                self.shutdown()
                
        
    def shutdown(self):
        self.device_2.set_channel(1) # x
        self.device_2.zero_field()
        
        self.device_z.zero_field()
        self.device_2.set_channel(2) # y
        self.device_2.zero_field()

        try:
            self.device_z.disconnect()
            self.device_2.disconnect()
            log.error("System was unable to cool down, system has disconnected.")
            raise ValueError("System was unable to cool down, system has disconnected.")
        except:
            print("No device z to disconect")
            print("No device 2 to disconect")
            log.error("System was unable to cool down, system has disconnected.")
            raise ValueError("System was unable to cool down, system has disconnected.")
            

class Magnet_highZ:
    
    ATOL = 1e-3
    def __init__(self, limit = 40):
        self.device_z = MagPowSup('169.254.62.187')
        self.device_2 = MagPowSup('169.254.62.188')
        self._field_difference_cutoff = 1e-3 #1e-5 # 0.1 G
        self._field_mag_lim = limit # bootleg version is kG, previous auttodry gui was T
        # self._B_sign = 1 #Not sure what this is for. Delete? 2025/01/24 - Orion and Ethan

        # limit such that below this field change the magnet does not actually change field,
        # to limit commands sent to the magnet

        self._B_sign = 1 
        
        self._Toverheat = 4.55
        self._Tcooling = (self._Toverheat - 0.35)
        self._Tflag = (self._Toverheat - 0.2)
        self._flag = 1


        # self.Bx_set, self.By_set, self.Bz_set = self.get_field_cartesian()
        # self.B_set, self.phi_set, self.theta_set = self.get_field_polar()

    def connecthighZ(self):
        self.device_z.disconnect()
        self.device_2.disconnect()

        if self.device_z.instrument is None:
            self.device_z.connect()
        if self.device_2.instrument is None:
            self.device_2.connect()        
        
        self.device_z.write("REMOTE")
        self.device_2.write("REMOTE")
        Bx, By, Bz = self.get_field_cartesian()
        print("Connecting. The field is", np.sqrt(Bx*Bx + By*By + Bz*Bz))
        
        self.Bx, self.By, self.Bz = self.get_field_cartesian()

        self.quench_check()
        self.voltage_check()
        
        if np.abs(Bz) > 9.9:
            if np.abs(Bx) > 0 or np.abs(By) > 0:
                self.device_z.disconnect()
                self.device_2.disconnect()
                print("Bmag vector is larger than 0.9 T! Don't touch anything else! Call Ethan or Kelly")
                raise ValueError("Bmag vector is larger than 0.9 T! Don't touch anything else! Call Ethan or Kelly")
            else:
                print("Not zeroing Bx and By, because if useful, you were already screwed.")
        else:
            print("Zeroing X magnet")
            self.device_2.set_channel(1)
            self.device_2.zero_field()

            print("Zeroing Y magnet")
            self.device_2.set_channel(2)
            self.device_2.zero_field()

        print("disconnecting from x and y for safety")
        self.device_2.disconnect()
        
    def voltage_check(self):
        zvolt = self.device_z.query("VOUT?")
        print(zvolt)

        
    def quench_check(self):
        zquench = self.device_z.query("*STB?")
        binary_form = format(ord(zquench), '08b')
        # print(binary_form[-3])
        if (binary_form[-3] == '1') :
            print("Quench in Z")
            
        self.device_2.set_channel(1) # x
        xquench = self.device_2.query("*STB?")
        binary_form = format(ord(xquench), '08b')
        # print(binary_form[-3])
        if (binary_form[-3] == '1') :
            print("Quench in X")
        
        self.device_2.set_channel(2) # y
        yquench = self.device_2.query("*STB?")
        binary_form = format(ord(yquench), '08b')
        # print(binary_form[-3])
        if (binary_form[-3] == '1') :
            print("Quench in Y")
        
    def get_Bz(self):
        """Returns the magnitude of the field."""
        return np.sqrt(self.Bz**2)

    def set_field_highZ(self, Bz):
        log.info('Setting Bz to : %g'%(Bz))
        if np.abs(self.Bz) > self._field_mag_lim: #np.sqrt returns positive square root
            log.error("A large field of %g was requested"%Bz)
            raise ValueError("Large field requested! Limit is %g"%self._field_mag_lim)
        
        self.device_z.set_field(Bz)
        
    def setSafe_wait_highZ(self, Bzset):
        # print("1")
        tic = time()
        # print("2")
        Bz_init = self.get_field_highZ()
        # print("3")
        # print(f"Bz initial: {Bx_init, By_init, Bz_init}")
        mag_safe = self.check_temps()
        # print("4")
        # print(f"Mag safe 1 is {mag_safe}")
        if mag_safe != None:
            if not np.abs(Bzset) > np.abs(Bz_init): 
                # print("entering if")
                while not self.check_field_highZ(Bzset, 10*self.ATOL):
                    print("waiting for z to ramp down")
                    mag_safe = self.check_temps()
                    # print(f"Mag safe 3 is {mag_safe}")
                    sleep(0.1)
                    if mag_safe == True:
                        self.set_field_highZ(Bzset)
                        sleep(0.1)
                        print(f"waiting for z to ramp down {time()-tic}")
            while not self.check_field_highZ(Bzset, self.ATOL):
                mag_safe = self.check_temps()
                # print(f"Mag safe 4 is {mag_safe}")
                sleep(0.1)
                if mag_safe == True:
                    self.set_field_highZ(Bzset)
                    sleep(0.1)
                    print(f"waiting for mag for {time()-tic}")

    def get_field_highZ(self):
        Bz = self.device_z.get_field()
        return Bz
    
    def get_field_cartesian(self):
        """
        Returns the cartesian parameterization of the field in the order X, Y, Z.
        """
        # Bz, By, Bx = self.device.magnet.getH(0), self.device.magnet.getH(1), self.device.magnet.getH(2)
        self.device_2.set_channel(1) # x
        Bx = self.device_2.get_field()
        # print(Bx)
        self.device_2.set_channel(2) # y
        By = self.device_2.get_field()
        # print(By)
        Bz = self.device_z.get_field()
        # print(Bz)
        return Bx, By, Bz

    def check_field_highZ(self, Bset, ATOL):
            """Checks the current field value to make sure it is within absolute tolerance of setpoint """
            Bz = self.get_field_highZ()

            print(f"Currently Bz = {Bz}") #redundant, if you use the monkypatch for pymeasure

            if np.isclose(Bset, Bz, atol=ATOL):
                log.info("Field is close to the setpoint")
                return True
            else:
                log.info(f"Currently Bz = {Bz}")
                return False
            
    def pause_all(self):
        
        self.device_z.pause_field()                           
        check1 = self.device_z.is_ramping()
        # print(check1)
        if check1 != "Pause" or check1 != "Standby":
            self.device_z.pause_field()
            # print("Ramping Paused")
    
                
    def check_temps(self):
        """Checks the Magnet Thermometer Temperature to know if the ramp rate needs to be paused"""
        bigcheck = self.device_z.temp_check(self._Toverheat)
        shield = TM620.Tshield
        
        if bigcheck == True and shield <= 55:
            bigcheck == True
        else: 
            bigcheck == False
        
        # print(f"bigcheck 1 is {bigcheck}")
            
        if bigcheck != False:
            secondcheck = self.device_z.temp_check((self._Tflag))
            # print(secondcheck)
            cooldowncountdown = time()          
            if secondcheck == False or self._flag == 2:
                self._flag = 2
                print(f"Overheat flag is up")
                while self._flag != 1:
                    if (time() - cooldowncountdown) < 1800:
                        # print(f"Threshold is {self._Tcooling}")
                        # print(f"Flag is up")
                        zcheck = self.device_z.temp_check(self._Tcooling)
                        
                        # print(f"Zcheck 1 is {zcheck}")
                        
                        if zcheck == True:
                            self._flag = 1
                            print(f"FLAG IS NOW RESET after {time() - cooldowncountdown}")
                            return True
                        
                        else:
                            self.pause_all()
                            zcheck = self.device_z.temp_check(self._Tcooling)

                    else:
                        timeout = pd.Timestamp.now()
                        print(f"Magnet unable to cool down. Ramping down all magnets and ending the scan. {timeout}")
                        self.shutdown()
                    
            elif secondcheck == True:
                if self._flag == 1:
                    return True 
                
        else: 
            timeout = pd.Timestamp.now()
            if shield > 55:
                print(f"Shield is too hot, stop this, call Ethan ASAP before ramping magnet or Kelly {timeout}")
                self.shutdown()
            else:
                print(f"Magnet is too hot, stop this, call Ethan ASAP before ramping magnet or Kelly {timeout}")
                self.shutdown()
                
            return None
            
    def shutdown(self):
        """
        Shuts down each of the magnets individually
        """
        self.device_z.zero_field()
        
        try:
            self.device_z.disconnect()
            log.error("System was unable to cool down, system has disconnected.")
            raise ValueError("System was unable to cool down, system has disconnected.")
        except:
            print("No device z to disconect")
            log.error("System was unable to cool down, system has disconnected.")
            raise ValueError("System was unable to cool down, system has disconnected.")
