#!/usr/bin/env python3
"""
ROBOT PELAYAN DESA - VERSION 5.0 (ADVANCED & STABLE)
Dengan fitur wake word, continuous listening, face recognition, dan sistem yang lebih stabil
"""
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
import sqlite3
import datetime
import time
import subprocess
import tempfile
import threading
import queue
import atexit
import numpy as np
import re
import random
import cv2
import traceback
import logging
import shutil
import json
import hashlib
import urllib.request
import signal
from PIL import Image, ImageTk, ImageDraw, ImageFont
from pathlib import Path

# Setup logging yang lebih terstruktur
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/home/nalika/robot_desa.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RobotDesa")

# Setup environment
os.environ['DISPLAY'] = ':0'
os.environ['XAUTHORITY'] = '/home/nalika/.Xauthority'

# =============================================================================
# IMPORT CHECKS & INITIALIZATION
# =============================================================================

class ImportChecker:
    """Class untuk mengecek dan mengelola import modul"""
    
    @staticmethod
    def try_import(module_name, package_name=None):
        """Helper untuk check availability modul"""
        try:
            if package_name is None:
                package_name = module_name
            exec(f"import {module_name}")
            logger.info(f"SUCCESS {package_name}: OK")
            return True
        except ImportError as e:
            logger.error(f"ERROR {package_name}: {e}")
            return False
    
    @staticmethod
    def check_all_dependencies():
        """Cek semua dependencies yang diperlukan"""
        dependencies = [
            ('PIL', 'PIL/Pillow'),
            ('pygame', 'Pygame'),
            ('gtts', 'gTTS'),
            ('speech_recognition', 'SpeechRecognition'),
            ('pytesseract', 'Tesseract OCR'),
            ('lgpio', 'lgpio'),
            ('picamera2', 'Picamera2'),
            ('cv2', 'OpenCV')
        ]
        
        results = {}
        for module, package in dependencies:
            results[module] = ImportChecker.try_import(module, package)
        
        return results

# Check available modules
DEPENDENCIES = ImportChecker.check_all_dependencies()
PIL_AVAILABLE = DEPENDENCIES.get('PIL', False)
PYGAME_AVAILABLE = DEPENDENCIES.get('pygame', False)
GTTS_AVAILABLE = DEPENDENCIES.get('gtts', False)
SPEECH_RECOGNITION_AVAILABLE = DEPENDENCIES.get('speech_recognition', False)
TESSERACT_AVAILABLE = DEPENDENCIES.get('pytesseract', False)
LGPIO_AVAILABLE = DEPENDENCIES.get('lgpio', False)
PICAMERA2_AVAILABLE = DEPENDENCIES.get('picamera2', False)
CV2_AVAILABLE = DEPENDENCIES.get('cv2', False)

# Initialize pygame mixer jika available
if PYGAME_AVAILABLE:
    try:
        import pygame
        pygame.mixer.init()
    except Exception as e:
        logger.error(f"ERROR Pygame mixer initialization: {e}")
        PYGAME_AVAILABLE = False

# Import conditional modules
if GTTS_AVAILABLE:
    from gtts import gTTS
if SPEECH_RECOGNITION_AVAILABLE:
    import speech_recognition as sr
if TESSERACT_AVAILABLE:
    import pytesseract
if LGPIO_AVAILABLE:
    import lgpio
if PICAMERA2_AVAILABLE:
    from picamera2 import Picamera2

# =============================================================================
# CONFIGURATION SYSTEM
# =============================================================================

class ConfigManager:
    """Manajemen konfigurasi aplikasi"""
    
    DEFAULT_CONFIG = {
        'database_path': str(Path.home() / "robot_desa.db"),
        'backup_dir': str(Path.home() / "backups"),
        'photo_dir': str(Path.home() / "foto_penduduk"),
        'face_model_path': str(Path.home() / "face_model.yml"),
        'face_database_path': str(Path.home() / "face_database.json"),
        'cascade_dir': str(Path.home() / "cascade_files"),
        'voice_speed': 150,
        'wake_word_enabled': True,
        'continuous_listening': False,
        'face_recognition_enabled': False,
        'face_detection_enabled': False,
        'backup_interval_hours': 1,
        'preview_fps': 10,
        'auto_exit_timeout': 300  # 5 menit
    }
    
    def __init__(self):
        self.config_path = Path.home() / ".robot_desa_config.json"
        self.config = self.load_config()
        self.setup_directories()
        logger.info("SUCCESS Config Manager: READY")
    
    def load_config(self):
        """Load konfigurasi dari file atau gunakan default"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge dengan default config untuk memastikan semua key ada
                for key, value in self.DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            logger.error(f"ERROR Loading config: {e}")
        
        # Return default config jika gagal load
        return self.DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Simpan konfigurasi ke file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("SUCCESS Config saved")
        except Exception as e:
            logger.error(f"ERROR Saving config: {e}")
    
    def setup_directories(self):
        """Buat direktori yang diperlukan"""
        directories = [
            self.config['backup_dir'],
            self.config['photo_dir'],
            self.config['cascade_dir']
        ]
        
        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                logger.info(f"SUCCESS Created directory: {directory}")
            except Exception as e:
                logger.error(f"ERROR Creating directory {directory}: {e}")
    
    def get(self, key, default=None):
        """Dapatkan nilai konfigurasi dengan fallback"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set nilai konfigurasi"""
        self.config[key] = value
        self.save_config()

# Inisialisasi Config Manager
config = ConfigManager()

# =============================================================================
# SUPPORTING CLASSES (Harus didefinisikan SEBELUM digunakan)
# =============================================================================

class DatabaseManager:
    def __init__(self):
        """Initialize database manager dengan path yang dinamis"""
        self.db_path = config.get('database_path')
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Table untuk data warga
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS warga (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nik TEXT UNIQUE,
                    nama TEXT,
                    alamat TEXT,
                    tanggal_lahir TEXT,
                    pekerjaan TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table untuk surat-surat
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS surat (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    jenis_surat TEXT,
                    nik TEXT,
                    nama TEXT,
                    nomor_surat TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table untuk achievements
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    achievement_id TEXT,
                    achievement_name TEXT,
                    points INTEGER,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table untuk activity points
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    activity_type TEXT,
                    points INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table untuk logs sistem
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    level TEXT,
                    message TEXT,
                    source TEXT
                )
            ''')
            conn.commit()
            conn.close()
            logger.info("SUCCESS Database initialized successfully")
        except Exception as e:
            logger.error(f"ERROR Database initialization error: {e}")
    
    def log_system_event(self, level, message, source="system"):
        """Log event sistem ke database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_logs (level, message, source)
                VALUES (?, ?, ?)
            ''', (level, message, source))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"ERROR Failed to log system event: {e}")
    
    def cari_warga(self, nik):
        """Cari data warga berdasarkan NIK dengan parameterized query"""
        if not nik or len(nik) != 16 or not nik.isdigit():
            logger.warning("INVALID NIK format provided")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM warga WHERE nik = ?", (nik,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'nik': result[1],
                    'nama': result[2],
                    'alamat': result[3],
                    'tanggal_lahir': result[4],
                    'pekerjaan': result[5]
                }
            return None
        except Exception as e:
            logger.error(f"ERROR Error searching warga: {e}")
            return None
    
    def get_all_warga(self):
        """Get semua data warga"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM warga ORDER BY nama")
            results = cursor.fetchall()
            conn.close()
            
            warga_list = []
            for result in results:
                warga_list.append({
                    'nik': result[1],
                    'nama': result[2],
                    'alamat': result[3],
                    'tanggal_lahir': result[4],
                    'pekerjaan': result[5]
                })
            return warga_list
        except Exception as e:
            logger.error(f"ERROR Error getting all warga: {e}")
            return []
    
    def simpan_surat(self, jenis_surat, nik, nama, content):
        """Simpan data surat ke database"""
        try:
            nomor_surat = f"{jenis_surat}/{datetime.datetime.now().strftime('%Y%m%d')}/{random.randint(100, 999)}"
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO surat (jenis_surat, nik, nama, nomor_surat, content)
                VALUES (?, ?, ?, ?, ?)
            ''', (jenis_surat, nik, nama, nomor_surat, content))
            conn.commit()
            conn.close()
            logger.info(f"SUCCESS Surat {jenis_surat} saved for {nama}")
            return nomor_surat
        except Exception as e:
            logger.error(f"ERROR Error saving surat: {e}")
            return None
    
    def add_warga(self, nik, nama, alamat, tanggal_lahir, pekerjaan):
        """Tambah data warga baru"""
        if not all([nik, nama, alamat, tanggal_lahir, pekerjaan]):
            logger.warning("Incomplete warga data provided")
            return False
        
        if len(nik) != 16 or not nik.isdigit():
            logger.warning("Invalid NIK format")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO warga (nik, nama, alamat, tanggal_lahir, pekerjaan)
                VALUES (?, ?, ?, ?, ?)
            ''', (nik, nama, alamat, tanggal_lahir, pekerjaan))
            conn.commit()
            conn.close()
            logger.info(f"SUCCESS Warga {nama} added/updated")
            return True
        except Exception as e:
            logger.error(f"ERROR Error adding warga: {e}")
            return False

class ServoController:
    def __init__(self):
        """Initialize servo controller"""
        self.servo_available = LGPIO_AVAILABLE
        self.gpio_handle = None
        self.servo_pins = {
            'hand': 17,
            'head': 18
        }
        
        if self.servo_available:
            try:
                self.gpio_handle = lgpio.gpiochip_open(0)
                # Setup GPIO pins sebagai output
                for pin in self.servo_pins.values():
                    lgpio.gpio_claim_output(self.gpio_handle, pin)
                logger.info("SUCCESS Servo Controller: READY")
            except Exception as e:
                logger.error(f"ERROR Servo Controller: UNAVAILABLE - {e}")
                self.servo_available = False
        else:
            logger.info("INFO Servo Controller: SIMULATION MODE")
    
    def wave_hand(self):
        """Simulate waving hand"""
        logger.info("ACTION Servo: Waving hand")
        if self.servo_available and self.gpio_handle:
            try:
                pin = self.servo_pins['hand']
                # Simulasi gerakan wave dengan PWM
                for _ in range(3):  # 3 kali wave
                    lgpio.tx_servo(self.gpio_handle, pin, 1000)  # Position 1
                    time.sleep(0.5)
                    lgpio.tx_servo(self.gpio_handle, pin, 2000)  # Position 2
                    time.sleep(0.5)
                lgpio.tx_servo(self.gpio_handle, pin, 1500)  # Position default
                return True
            except Exception as e:
                logger.error(f"ERROR Wave hand failed: {e}")
        else:
            # Simulation mode
            time.sleep(1)
            return True
    
    def nod_head(self):
        """Simulate nodding head"""
        logger.info("ACTION Servo: Nodding head")
        if self.servo_available and self.gpio_handle:
            try:
                pin = self.servo_pins['head']
                # Simulasi mengangguk
                for _ in range(2):  # 2 kali angguk
                    lgpio.tx_servo(self.gpio_handle, pin, 1200)  # Down
                    time.sleep(0.3)
                    lgpio.tx_servo(self.gpio_handle, pin, 1800)  # Up
                    time.sleep(0.3)
                lgpio.tx_servo(self.gpio_handle, pin, 1500)  # Default
                return True
            except Exception as e:
                logger.error(f"ERROR Nod head failed: {e}")
        else:
            # Simulation mode
            time.sleep(1)
            return True
    
    def reset_all_servos(self):
        """Reset all servos to default position"""
        logger.info("ACTION Servo: Reset all servos")
        if self.servo_available and self.gpio_handle:
            try:
                for pin in self.servo_pins.values():
                    lgpio.tx_servo(self.gpio_handle, pin, 1500)  # Default position
                return True
            except Exception as e:
                logger.error(f"ERROR Reset servos failed: {e}")
        return True
    
    def cleanup(self):
        """Cleanup servo resources"""
        if self.servo_available and self.gpio_handle:
            try:
                self.reset_all_servos()
                lgpio.gpiochip_close(self.gpio_handle)
                logger.info("SUCCESS Servo Controller: CLEANED UP")
            except Exception as e:
                logger.error(f"ERROR Servo cleanup failed: {e}")

class OCRSystem:
    def __init__(self):
        """Initialize OCR system"""
        self.ocr_available = TESSERACT_AVAILABLE and CV2_AVAILABLE
        logger.info(f"SUCCESS OCR System: {'READY' if self.ocr_available else 'SIMULATION MODE'}")
        
        # Set path Tesseract jika tersedia
        if self.ocr_available:
            try:
                pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
            except Exception as e:
                logger.warning(f"WARNING Tesseract path setup: {e}")
    
    def extract_nik_from_image(self, image_path):
        """Extract NIK from image using OCR dengan error handling yang lebih baik"""
        if not os.path.exists(image_path):
            logger.error(f"ERROR Image not found: {image_path}")
            return None
            
        if not self.ocr_available:
            # Simulation mode - return random NIK for testing
            simulated_nik = f"327301010101{random.randint(1000,9999)}"
            logger.info(f"SIMULATION OCR returning simulated NIK: {simulated_nik}")
            return simulated_nik
        
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"ERROR Failed to load image: {image_path}")
                return None
                
            # Preprocess image for better OCR
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Apply noise reduction
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            # Apply thresholding
            thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            # Apply morphological operations to clean up text
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # OCR with specific configuration for numbers
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(cleaned, config=custom_config, lang='ind')
            
            logger.info(f"OCR Raw result: {text}")
            
            # Extract 16-digit numbers (NIK format)
            numbers = re.findall(r'\d{16}', text)
            if numbers:
                return numbers[0]
            else:
                # Coba metode alternatif jika tidak menemukan 16 digit berturut-turut
                all_digits = ''.join(re.findall(r'\d+', text))
                if len(all_digits) >= 16:
                    # Ambil 16 digit pertama
                    return all_digits[:16]
                
            logger.warning("WARNING No valid NIK found in OCR result")
            return None
        except Exception as e:
            logger.error(f"ERROR OCR Error: {e}")
            traceback.print_exc()
            return None

class BackupSystem:
    def __init__(self):
        """Initialize backup system"""
        self.backup_dir = config.get('backup_dir')
        os.makedirs(self.backup_dir, exist_ok=True)
        logger.info("SUCCESS Backup System: READY")
    
    def auto_backup(self):
        """Perform automatic backup"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_dir, f"backup_{timestamp}.db")
            db_path = config.get('database_path')
            
            if not os.path.exists(db_path):
                logger.error(f"ERROR Database file not found: {db_path}")
                return False
                
            # Copy database file
            shutil.copy2(db_path, backup_file)
            
            # Keep only last 10 backups
            backups = sorted([f for f in os.listdir(self.backup_dir) if f.startswith('backup_')])
            if len(backbacks) > 10:
                for old_backup in backups[:-10]:
                    os.remove(os.path.join(self.backup_dir, old_backup))
            
            logger.info(f"SUCCESS Backup created: {backup_file}")
            return True
        except Exception as e:
            logger.error(f"ERROR Backup error: {e}")
            return False
    
    def start_auto_backup_scheduler(self):
        """Start automatic backup scheduler"""
        backup_interval = config.get('backup_interval_hours', 1) * 3600
        
        def backup_scheduler():
            while True:
                time.sleep(backup_interval)
                self.auto_backup()
        
        threading.Thread(target=backup_scheduler, daemon=True, name="BackupThread").start()
        logger.info(f"SUCCESS Auto backup scheduler: STARTED (interval: {backup_interval//3600} hours)")

class WeatherService:
    def __init__(self):
        """Initialize weather service"""
        self.has_internet = self.check_internet()
        logger.info(f"SUCCESS Weather Service: {'READY' if self.has_internet else 'NO INTERNET'}")
    
    def check_internet(self):
        """Check internet connection"""
        try:
            import urllib.request
            urllib.request.urlopen('https://8.8.8.8', timeout=5)
            return True
        except:
            return False
    
    def get_weather(self):
        """Get weather information"""
        if not self.has_internet:
            return "Tidak dapat mengakses info cuaca (tidak ada internet)"
            
        try:
            # Di implementasi nyata, kita akan menggunakan API weather
            # Untuk sekarang kita simulasikan
            weather_conditions = [
                "Cerah", "Cerah Berawan", "Berawan", "Hujan Ringan", 
                "Hujan Sedang", "Hujan Lebat"
            ]
            temperatures = range(25, 35)
            condition = random.choice(weather_conditions)
            temperature = random.choice(temperatures)
            return f"Cuaca hari ini: {condition}, Suhu: {temperature}°C"
        except Exception as e:
            logger.error(f"ERROR Weather service error: {e}")
            return "Tidak dapat mengambil info cuaca saat ini"

class EnhancedConversationManager:
    def __init__(self, voice_system, database_manager):
        """Initialize enhanced conversation manager"""
        self.voice = voice_system
        self.db = database_manager
        self.conversation_context = {}
        self.conversation_history = []
        logger.info("SUCCESS Enhanced Conversation Manager: READY")
    
    def process_contextual_conversation(self, text):
        """Process contextual conversation"""
        text_lower = text.lower()
        
        # Greetings
        if any(word in text_lower for word in ['halo', 'hai', 'hei', 'hallo']):
            response = "Halo! Selamat datang di layanan desa. Ada yang bisa saya bantu?"
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # How are you
        elif any(word in text_lower for word in ['apa kabar', 'how are you', 'bagaimana kabarmu', 'kabar']):
            response = "Saya baik-baik saja, terima kasih! Siap membantu Anda hari ini."
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # Thank you
        elif any(word in text_lower for word in ['terima kasih', 'thanks', 'thank you', 'makasih']):
            response = "Sama-sama! Senang bisa membantu Anda."
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # What's your name
        elif any(word in text_lower for word in ['siapa namamu', 'what is your name', 'nama kamu', 'kamu siapa']):
            response = "Saya Ojan, asisten pelayan desa. Senang berkenalan dengan Anda!"
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # Help
        elif any(word in text_lower for word in ['bantuan', 'help', 'tolong', 'bisa apa saja']):
            response = "Saya bisa membantu Anda dengan: layanan surat, informasi warga, foto, scan dokumen, dan berbagai layanan desa lainnya."
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # Weather
        elif any(word in text_lower for word in ['cuaca', 'weather', 'hujan', 'panas', 'dingin']):
            weather_service = WeatherService()
            weather_info = weather_service.get_weather()
            response = f"Informasi cuaca: {weather_info}"
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # Time
        elif any(word in text_lower for word in ['jam berapa', 'waktu', 'sekarang jam', 'pukul berapa']):
            current_time = datetime.datetime.now().strftime("%H:%M")
            response = f"Sekarang jam {current_time}"
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        # Date
        elif any(word in text_lower for word in ['hari apa', 'tanggal berapa', 'sekarang tanggal', 'hari ini']):
            current_date = datetime.datetime.now().strftime("%d %B %Y")
            current_day = datetime.datetime.now().strftime("%A")
            days = {
                'Monday': 'Senin',
                'Tuesday': 'Selasa', 
                'Wednesday': 'Rabu',
                'Thursday': 'Kamis',
                'Friday': 'Jumat',
                'Saturday': 'Sabtu',
                'Sunday': 'Minggu'
            }
            response = f"Hari ini {days.get(current_day, current_day)}, tanggal {current_date}"
            self.voice.speak(response)
            self.add_to_history("system", response)
            return response
        
        return None
    
    def add_to_history(self, sender, message):
        """Tambahkan pesan ke history percakapan"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conversation_history.append({
            'timestamp': timestamp,
            'sender': sender,
            'message': message
        })
        
        # Batasi history hanya 50 pesan terakhir
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]

class GamificationSystem:
    def __init__(self):
        """Initialize gamification system"""
        self.db = DatabaseManager()
        self.achievements = {
            'first_use': {'name': 'Pengguna Pertama', 'points': 10, 'description': 'Menggunakan sistem untuk pertama kali'},
            'voice_command': {'name': 'Ahli Perintah Suara', 'points': 15, 'description': 'Menggunakan perintah suara'},
            'face_detected': {'name': 'Wajah Terdeteksi', 'points': 20, 'description': 'Wajah berhasil terdeteksi'},
            'face_recognized': {'name': 'Wajah Dikenali', 'points': 30, 'description': 'Wajah berhasil dikenali'},
            'photo_taken': {'name': 'Fotografer Handal', 'points': 15, 'description': 'Berhasil mengambil foto'},
            'document_scan': {'name': 'Pemindai Dokumen', 'points': 25, 'description': 'Berhasil memindai dokumen'},
            'service_completed': {'name': 'Pelayan Masyarakat', 'points': 30, 'description': 'Menyelesaikan layanan'},
            'data_entry': {'name': 'Pendata Handal', 'points': 20, 'description': 'Menambahkan data warga baru'}
        }
        logger.info("SUCCESS Gamification System: READY")
    
    def unlock_achievement(self, user_id, achievement_id):
        """Unlock achievement for user"""
        try:
            if achievement_id not in self.achievements:
                logger.warning(f"WARNING Achievement ID tidak valid: {achievement_id}")
                return False
                
            achievement = self.achievements[achievement_id]
            
            # Check if already unlocked
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM achievements 
                WHERE user_id = ? AND achievement_id = ?
            ''', (user_id, achievement_id))
            
            if not cursor.fetchone():
                # Insert new achievement
                cursor.execute('''
                    INSERT INTO achievements (user_id, achievement_id, achievement_name, points)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, achievement_id, achievement['name'], achievement['points']))
                conn.commit()
                
                # Tambahkan ke log sistem
                self.db.log_system_event("INFO", f"Achievement unlocked: {achievement['name']} (+{achievement['points']} points)", user_id)
                
                logger.info(f"SUCCESS Achievement unlocked: {achievement['name']} (+{achievement['points']} points)")
                return True
            
            conn.close()
            return False
            
        except Exception as e:
            logger.error(f"ERROR Error unlocking achievement: {e}")
            return False
    
    def add_activity_point(self, user_id, activity_type, points):
        """Add activity points for user"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_points (user_id, activity_type, points)
                VALUES (?, ?, ?)
            ''', (user_id, activity_type, points))
            conn.commit()
            conn.close()
            
            # Tambahkan ke log sistem
            self.db.log_system_event("INFO", f"Activity points added: {activity_type} (+{points} points)", user_id)
            
            logger.info(f"SUCCESS Activity points added: {activity_type} (+{points} points)")
            return True
        except Exception as e:
            logger.error(f"ERROR Error adding activity points: {e}")
            return False
    
    def get_user_stats(self, user_id):
        """Get user statistics"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            # Total points
            cursor.execute('SELECT SUM(points) FROM user_points WHERE user_id = ?', (user_id,))
            total_points = cursor.fetchone()[0] or 0
            # Total achievements
            cursor.execute('SELECT COUNT(*) FROM achievements WHERE user_id = ?', (user_id,))
            total_achievements = cursor.fetchone()[0] or 0
            conn.close()
            return {
                'total_points': total_points,
                'total_achievements': total_achievements
            }
        except Exception as e:
            logger.error(f"ERROR Error getting user stats: {e}")
            return {'total_points': 0, 'total_achievements': 0}
    
    def get_user_achievements(self, user_id):
        """Get user achievements"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT achievement_name, points, unlocked_at 
                FROM achievements 
                WHERE user_id = ? 
                ORDER BY unlocked_at DESC
            ''', (user_id,))
            achievements = []
            for row in cursor.fetchall():
                achievements.append({
                    'name': row[0],
                    'points': row[1],
                    'unlocked_at': row[2]
                })
            conn.close()
            return achievements
        except Exception as e:
            logger.error(f"ERROR Error getting user achievements: {e}")
            return []
    
    def get_leaderboard(self, limit=10):
        """Get leaderboard"""
        try:
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, SUM(points) as total_points, COUNT(*) as total_achievements
                FROM (
                    SELECT user_id, points FROM user_points
                    UNION ALL
                    SELECT user_id, points FROM achievements
                )
                GROUP BY user_id
                ORDER BY total_points DESC
                LIMIT ?
            ''', (limit,))
            leaderboard = []
            for row in cursor.fetchall():
                leaderboard.append({
                    'user_id': row[0],
                    'total_points': row[1] or 0,
                    'total_achievements': row[2] or 0
                })
            conn.close()
            return leaderboard
        except Exception as e:
            logger.error(f"ERROR Error getting leaderboard: {e}")
            return []

# =============================================================================
# ADVANCED FACE RECOGNITION SYSTEM
# =============================================================================

class AdvancedFaceRecognition:
    def __init__(self):
        self.face_recognizer = None
        self.known_faces = {}  # {face_id: {'name': 'nama', 'embedding': data, 'images': []}}
        self.face_database = {}
        self.recognition_enabled = False
        self.recognition_threshold = 80  # Confidence threshold - lebih tinggi berarti lebih ketat
        self.face_detector = None
        self.model_path = config.get('face_model_path')
        self.database_path = config.get('face_database_path')
        self.setup_face_recognition()
    
    def setup_face_recognition(self):
        """Setup face recognition system dengan error handling yang lebih baik"""
        try:
            # Gunakan LBPH Face Recognizer (ringan untuk Raspberry Pi)
            if CV2_AVAILABLE:
                self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
                # Setup face detector
                self.face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                
                # Load trained model jika ada
                if os.path.exists(self.model_path):
                    self.face_recognizer.read(self.model_path)
                    logger.info("SUCCESS Face Recognition: MODEL LOADED")
                else:
                    logger.info("INFO Face Recognition: NO TRAINED MODEL - Training required")
                
                # Load face database
                self.load_face_database()
                self.recognition_enabled = True
                logger.info("SUCCESS Advanced Face Recognition: READY")
            else:
                logger.warning("WARNING OpenCV not available - Face recognition disabled")
                self.recognition_enabled = False
                
        except Exception as e:
            logger.error(f"ERROR Face Recognition setup failed: {e}")
            self.recognition_enabled = False
    
    def load_face_database(self):
        """Load database wajah dari file"""
        try:
            if os.path.exists(self.database_path):
                with open(self.database_path, 'r') as f:
                    self.face_database = json.load(f)
                logger.info(f"SUCCESS Loaded {len(self.face_database)} known faces")
            else:
                self.face_database = {}
                logger.info("INFO No existing face database found")
        except Exception as e:
            logger.error(f"ERROR Error loading face database: {e}")
            self.face_database = {}
    
    def save_face_database(self):
        """Simpan database wajah ke file"""
        try:
            with open(self.database_path, 'w') as f:
                json.dump(self.face_database, f, indent=2)
            logger.info("SUCCESS Face database saved")
        except Exception as e:
            logger.error(f"ERROR Error saving face database: {e}")
    
    def train_recognizer(self):
        """Train face recognizer dengan data yang ada"""
        if not self.face_database:
            logger.warning("WARNING No face data to train")
            return False
        
        try:
            faces = []
            labels = []
            label_map = {}
            current_label = 0
            
            for face_id, face_data in self.face_database.items():
                if 'images' not in face_data or not face_data['images']:
                    continue
                    
                for image_data in face_data['images']:
                    try:
                        # Decode image dari database
                        img_bytes = bytes.fromhex(image_data['image'])
                        nparr = np.frombuffer(img_bytes, np.uint8)
                        face_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
                        
                        if face_img is not None and face_img.size > 0:
                            # Resize untuk konsistensi
                            face_img = cv2.resize(face_img, (100, 100))
                            faces.append(face_img)
                            labels.append(current_label)
                            label_map[current_label] = face_id
                    except Exception as e:
                        logger.error(f"ERROR Error processing face image: {e}")
                        continue
                current_label += 1
            
            if faces and labels:
                # Train recognizer
                self.face_recognizer.train(faces, np.array(labels))
                # Save model
                self.face_recognizer.save(self.model_path)
                logger.info(f"SUCCESS Face recognizer trained with {len(faces)} images")
                return True
            else:
                logger.warning("WARNING No valid face images for training")
                return False
                
        except Exception as e:
            logger.error(f"ERROR Error training face recognizer: {e}")
            traceback.print_exc()
            return False
    
    def register_face(self, face_image, person_name, face_id=None):
        """Daftarkan wajah baru ke sistem"""
        try:
            if face_id is None:
                face_id = f"face_{len(self.face_database) + 1}_{int(time.time())}"
            
            # Convert face image to grayscale
            if len(face_image.shape) == 3:
                gray_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
            else:
                gray_face = face_image.copy()
            
            # Resize untuk konsistensi
            gray_face = cv2.resize(gray_face, (100, 100))
            
            # Convert to serializable format (hex)
            _, img_encoded = cv2.imencode('.jpg', gray_face, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            img_hex = img_encoded.tobytes().hex()
            
            # Tambahkan ke database
            if face_id not in self.face_database:
                self.face_database[face_id] = {
                    'name': person_name,
                    'registered_date': datetime.datetime.now().isoformat(),
                    'images': []
                }
            
            self.face_database[face_id]['images'].append({
                'image': img_hex,
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            # Batasi max 5 gambar per orang untuk efisiensi
            if len(self.face_database[face_id]['images']) > 5:
                self.face_database[face_id]['images'] = self.face_database[face_id]['images'][-5:]
            
            # Save database
            self.save_face_database()
            
            # Retrain recognizer
            success = self.train_recognizer()
            if success:
                logger.info(f"SUCCESS Face registered: {person_name} (ID: {face_id})")
                return face_id
            else:
                logger.error(f"ERROR Failed to train recognizer after registration")
                return None
                
        except Exception as e:
            logger.error(f"ERROR Error registering face: {e}")
            traceback.print_exc()
            return None
    
    def recognize_face(self, face_image):
        """Recognize wajah dari image dengan penanganan error yang lebih baik"""
        if not self.recognition_enabled or self.face_recognizer is None:
            return "unknown", 0, None
        
        try:
            if face_image is None or face_image.size == 0:
                logger.warning("WARNING Empty face image provided")
                return "unknown", 0, None
            
            # Convert to grayscale jika perlu
            if len(face_image.shape) == 3:
                gray_face = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
            else:
                gray_face = face_image.copy()
            
            # Resize untuk konsistensi
            gray_face = cv2.resize(gray_face, (100, 100))
            
            # Predict
            label, confidence = self.face_recognizer.predict(gray_face)
            
            # Confidence yang lebih rendah berarti lebih mirip
            # Konversi ke persentase confidence (semakin rendah nilai confidence, semakin mirip)
            similarity = max(0, 100 - confidence)
            
            if similarity > self.recognition_threshold:
                # Cari face_id berdasarkan label
                face_ids = list(self.face_database.keys())
                if 0 <= label < len(face_ids):
                    face_id = face_ids[label]
                    person_name = self.face_database[face_id]['name']
                    return person_name, similarity, face_id
            
            return "unknown", similarity, None
            
        except cv2.error as e:
            logger.error(f"OPENCV ERROR Face recognition: {e}")
            return "unknown", 0, None
        except Exception as e:
            logger.error(f"ERROR Face recognition error: {e}")
            traceback.print_exc()
            return "unknown", 0, None
    
    def detect_and_recognize_faces(self, frame):
        """Deteksi dan recognize semua wajah dalam frame"""
        recognized_faces = []
        if not self.recognition_enabled or self.face_detector is None:
            return frame, recognized_faces
        
        try:
            # Convert ke grayscale untuk deteksi
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame.copy()
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)  # Convert back to color for display
            
            # Deteksi wajah
            faces = self.face_detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            for (x, y, w, h) in faces:
                # Extract wajah
                face_roi = frame[y:y+h, x:x+w]
                # Recognize wajah
                name, confidence, face_id = self.recognize_face(face_roi)
                
                # Gambar bounding box
                if name != "unknown" and confidence > self.recognition_threshold:
                    color = (0, 255, 0)  # Hijau untuk wajah dikenal
                    label = f"{name} ({confidence:.1f}%)"
                else:
                    color = (0, 165, 255)  # Orange untuk wajah tidak dikenal
                    label = f"Unknown ({confidence:.1f}%)" if confidence > 0 else "Unknown"
                
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, label, (x, y-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                recognized_faces.append({
                    'name': name,
                    'confidence': confidence,
                    'face_id': face_id,
                    'position': (x, y, w, h)
                })
            
            return frame, recognized_faces
            
        except Exception as e:
            logger.error(f"ERROR Face detection/recognition error: {e}")
            traceback.print_exc()
            return frame, []

# =============================================================================
# ADVANCED VOICE SYSTEM
# =============================================================================

class AdvancedVoiceSystem:
    def __init__(self):
        self.has_internet = self.check_internet()
        self.command_queue = queue.Queue()
        self.listening = False
        self.conversation_manager = None
        self.recognizer = None
        self.microphone = None
        self.wake_word_detection = config.get('wake_word_enabled', True)
        self.continuous_listening = config.get('continuous_listening', False)
        self.voice_profiles = {}
        self.current_user = None
        self.voice_speed = config.get('voice_speed', 150)  # Default speed
        self.audio_queue = queue.Queue()
        self.processing_audio = False
        self.last_activity_time = time.time()
        self.auto_exit_timeout = config.get('auto_exit_timeout', 300)  # 5 menit
        
        # Setup logging
        self.logger = logging.getLogger("VoiceSystem")
        self.logger.setLevel(logging.INFO)
        
        logger.info(f"SUCCESS Voice System initialized - Internet: {'Available' if self.has_internet else 'Not Available'}")
    
    def set_conversation_manager(self, conversation_manager):
        """Set conversation manager"""
        self.conversation_manager = conversation_manager
    
    def check_internet(self):
        """Check koneksi internet"""
        try:
            import urllib.request
            urllib.request.urlopen('https://8.8.8.8', timeout=5)
            return True
        except:
            return False
    
    def speak(self, text, speed=None):
        """Text-to-speech functionality dengan kecepatan yang bisa disesuaikan"""
        if not text.strip():
            return
            
        if speed is None:
            speed = self.voice_speed
            
        self.logger.info(f"SPEAK: {text}")
        
        def speak_thread():
            try:
                if GTTS_AVAILABLE and self.has_internet:
                    self.speak_gtts(text)
                else:
                    self.speak_espeak(text, speed)
            except Exception as e:
                self.logger.error(f"ERROR TTS error: {e}")
                print(f"SPEAK (Fallback): {text}")
                try:
                    self.speak_espeak(text, speed)
                except:
                    pass
        
        # Start speaking in background thread
        threading.Thread(target=speak_thread, daemon=True, name="TTS_Thread").start()
    
    def speak_gtts(self, text):
        """Gunakan gTTS untuk text-to-speech"""
        try:
            tts = gTTS(text=text, lang='id')
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                temp_file = f.name
            tts.save(temp_file)
            
            if PYGAME_AVAILABLE:
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                pygame.mixer.music.unload()
            else:
                # Fallback ke play command jika pygame tidak tersedia
                subprocess.run(['mpg123', temp_file], capture_output=True, timeout=10)
            
            # Cleanup
            try:
                os.unlink(temp_file)
            except:
                pass
                
        except Exception as e:
            self.logger.error(f"ERROR gTTS error: {e}")
            self.speak_espeak(text)
    
    def speak_espeak(self, text, speed=150):
        """Gunakan espeak sebagai fallback dengan kecepatan bisa disesuaikan"""
        try:
            # Sanitize text untuk espeak
            safe_text = text.replace('"', "'").replace('\n', ' ')
            subprocess.run(['espeak', '-v', 'id', '-s', str(speed), f'"{safe_text}"'], 
                         capture_output=True, timeout=10)
        except Exception as e:
            self.logger.error(f"ERROR espeak error: {e}")
            print(f"SPEAK (Fallback console): {text}")
    
    def enable_wake_word(self):
        """Enable wake word detection"""
        self.wake_word_detection = True
        config.set('wake_word_enabled', True)
        self.logger.info("SUCCESS Wake word detection: ENABLED")
        return True
    
    def disable_wake_word(self):
        """Disable wake word detection"""
        self.wake_word_detection = False
        config.set('wake_word_enabled', False)
        self.logger.info("SUCCESS Wake word detection: DISABLED")
        return True
    
    def enable_continuous_listening(self):
        """Enable continuous listening mode"""
        self.continuous_listening = True
        config.set('continuous_listening', True)
        self.logger.info("SUCCESS Continuous listening: ENABLED")
        return True
    
    def disable_continuous_listening(self):
        """Disable continuous listening mode"""
        self.continuous_listening = False
        config.set('continuous_listening', False)
        self.logger.info("SUCCESS Continuous listening: DISABLED")
        return True
    
    def detect_wake_word(self, text):
        """Deteksi wake word dalam text"""
        wake_words = ['ojan', 'halo ojan', 'hei ojan', 'hai ojan', 'oy ojan']
        text_lower = text.lower()
        return any(wake_word in text_lower for wake_word in wake_words)
    
    def start_listening(self):
        """START LISTENING DENGAN FITUR ADVANCED"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.logger.error("ERROR Voice recognition tidak tersedia")
            return False
        
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise
            with self.microphone as source:
                self.logger.info("ADJUSTING Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            self.listening = True
            self.voice_thread = threading.Thread(target=self._advanced_listen_loop, daemon=True, name="VoiceRecognitionThread")
            self.voice_thread.start()
            self.logger.info("SUCCESS Advanced Voice recognition: READY")
            return True
        except Exception as e:
            self.logger.error(f"ERROR Voice recognition initialization error: {e}")
            traceback.print_exc()
            return False
    
    def stop_listening(self):
        """Stop voice recognition"""
        self.listening = False
        self.logger.info("SUCCESS Voice recognition stopped")
    
    def _advanced_listen_loop(self):
        """LOOP MENDENGARKAN DENGAN FITUR WAKE WORD"""
        self.logger.info("VOICE Advanced Voice recognition aktif...")
        self.logger.info("INFO Katakan 'Ojan' untuk membangunkan saya")
        
        # Check apakah offline mode
        offline_mode = not self.check_internet()
        if offline_mode:
            self.logger.warning("WARNING Operating in offline mode - limited voice recognition")
        
        while self.listening:
            try:
                # Check for auto-exit due to inactivity
                if time.time() - self.last_activity_time > self.auto_exit_timeout:
                    self.logger.info(f"INFO Auto-exit due to inactivity after {self.auto_exit_timeout} seconds")
                    self.speak("Sistem akan mati karena tidak ada aktivitas. Sampai jumpa!")
                    time.sleep(3)
                    os._exit(0)
                
                if self.wake_word_detection and not self.continuous_listening:
                    # Mode wake word - tunggu wake word dulu
                    self.logger.debug("WAITING Menunggu wake word...")
                    with self.microphone as source:
                        audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=3)
                    self.last_activity_time = time.time()
                    
                    if offline_mode:
                        text = self.recognizer.recognize_sphinx(audio, language="id-ID").lower()
                    else:
                        text = self.recognizer.recognize_google(audio, language="id-ID").lower()
                    
                    self.logger.info(f"HEARD Wake word attempt: {text}")
                    
                    if self.detect_wake_word(text):
                        self.logger.info("WAKE Wake word terdeteksi! Mendengarkan perintah...")
                        self.speak("Ya, ada yang bisa saya bantu?", 160)
                        
                        # Sekarang dengarkan perintah maksimal 5 detik
                        with self.microphone as source:
                            audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=5)
                        self.last_activity_time = time.time()
                        
                        if offline_mode:
                            command_text = self.recognizer.recognize_sphinx(audio, language="id-ID").lower()
                        else:
                            command_text = self.recognizer.recognize_google(audio, language="id-ID").lower()
                        
                        self.logger.info(f"COMMAND Perintah: {command_text}")
                        command = self.process_advanced_voice_command(command_text)
                        if command:
                            self.command_queue.put(command)
                else:
                    # Mode continuous listening atau tanpa wake word
                    self.logger.debug("LISTENING Mendengarkan...")
                    with self.microphone as source:
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    self.last_activity_time = time.time()
                    
                    if offline_mode:
                        text = self.recognizer.recognize_sphinx(audio, language="id-ID").lower()
                    else:
                        text = self.recognizer.recognize_google(audio, language="id-ID").lower()
                    
                    self.logger.info(f"HEARD Terdengar: {text}")
                    
                    # Jika dalam mode wake word, cek apakah ada wake word
                    if self.wake_word_detection:
                        if self.detect_wake_word(text):
                            self.logger.info("WAKE Wake word terdeteksi dalam percakapan!")
                            # Hapus wake word dari text
                            for wake_word in ['ojan', 'halo ojan', 'hei ojan', 'hai ojan', 'oy ojan']:
                                text = text.replace(wake_word, '').strip()
                            
                            if text:  # Jika masih ada perintah setelah wake word
                                command = self.process_advanced_voice_command(text)
                                if command:
                                    self.command_queue.put(command)
                        else:
                            # Tidak ada wake word, abaikan
                            continue
                    else:
                        # Tanpa wake word, proses semua perintah
                        command = self.process_advanced_voice_command(text)
                        if command:
                            self.command_queue.put(command)
            
            except sr.WaitTimeoutError:
                # Timeout, continue listening
                continue
            except sr.UnknownValueError:
                # Tidak bisa memahami suara
                continue
            except Exception as e:
                self.logger.error(f"ERROR Voice listening error: {e}")
                # Reset recognizer jika terjadi error berulang
                try:
                    self.recognizer = sr.Recognizer()
                except:
                    pass
                continue
    
    def process_advanced_voice_command(self, text):
        """PROSES PERINTAH SUARA DENGAN FITUR LANJUTAN"""
        text = text.lower()
        self.logger.info(f"COMMAND Memproses perintah: {text}")
        
        # Perintah sistem voice
        if any(word in text for word in ['bangunkan', 'wake word', 'bangun', 'aktifkan wake']):
            if 'aktif' in text or 'nyala' in text or 'hidup' in text:
                return 'enable_wake_word'
            elif 'mati' in text or 'nonaktif' in text or 'matikan' in text:
                return 'disable_wake_word'
        
        elif any(word in text for word in ['dengarkan terus', 'continuous listening', 'terus mendengar']):
            if 'aktif' in text or 'nyala' in text or 'hidup' in text:
                return 'enable_continuous_listening'
            elif 'mati' in text or 'nonaktif' in text or 'matikan' in text:
                return 'disable_continuous_listening'
        
        # Perintah face recognition
        elif any(word in text for word in ['kenali wajah', 'face recognition', 'registrasi wajah', 'daftar wajah']):
            if any(word in text for word in ['aktif', 'nyala', 'hidup', 'mulai']):
                return 'enable_face_recognition'
            elif any(word in text for word in ['mati', 'nonaktif', 'berhenti', 'stop']):
                return 'disable_face_recognition'
            elif any(word in text for word in ['daftar', 'registrasi', 'tambah']):
                return 'register_face'
        
        # Perintah kecepatan suara
        elif any(word in text for word in ['cepat', 'lambat', 'kecepatan suara', 'speed']):
            if 'cepat' in text or 'tingkatkan' in text:
                return 'set_voice_fast'
            elif 'lambat' in text or 'turunkan' in text:
                return 'set_voice_slow'
            elif 'normal' in text or 'standar' in text:
                return 'set_voice_normal'
        
        # Perintah face detection
        elif any(word in text for word in ['deteksi wajah', 'detek wajah', 'wajah']):
            if any(word in text for word in ['aktif', 'nyala', 'hidup', 'mulai', 'on']):
                return 'enable_face_detection'
            elif any(word in text for word in ['mati', 'nonaktif', 'berhenti', 'stop', 'off']):
                return 'disable_face_detection'
        
        # PERINTAH KONTEKSTUAL (dari sebelumnya)
        elif any(word in text for word in ['jam berapa', 'waktu', 'sekarang jam', 'pukul']):
            return 'get_time'
        
        elif any(word in text for word in ['hari apa', 'tanggal berapa', 'sekarang tanggal']):
            return 'get_date'
        
        elif any(word in text for word in ['cuaca', 'weather', 'hujan', 'panas']):
            return 'get_weather'
        
        elif any(word in text for word in ['achievement', 'prestasi', 'point', 'skor', 'poin']):
            return 'show_achievements'
        
        elif any(word in text for word in ['leaderboard', 'peringkat', 'ranking', 'juara']):
            return 'show_leaderboard'
        
        # PERINTAH KAMERA
        elif any(word in text for word in ['kamera', 'camera', 'webcam']):
            if any(word in text for word in ['hidup', 'nyala', 'start', 'aktifkan', 'on']):
                return 'start_camera'
            elif any(word in text for word in ['mati', 'stop', 'nonaktifkan', 'matikan', 'off']):
                return 'stop_camera'
            elif any(word in text for word in ['foto', 'ambil', 'capture', 'jepret']):
                return 'capture_photo'
            elif any(word in text for word in ['baca', 'scan', 'nik', 'ktp']):
                return 'scan_document'
        
        # Perintah servo
        elif any(word in text for word in ['lambaikan', 'tangan', 'wave', 'gerakkan tangan']):
            return 'wave_hand'
        
        elif any(word in text for word in ['angguk', 'kepala', 'nod', 'gerakkan kepala']):
            return 'nod_head'
        
        # Service commands
        elif any(word in text for word in ['sktm', 'tidak mampu', 'miskin']):
            return 'service_sktm'
        
        elif any(word in text for word in ['domisili', 'domisil', 'tinggal']):
            return 'service_domisili'
        
        elif any(word in text for word in ['usaha', 'dagang', 'bisnis']):
            return 'service_usaha'
        
        elif any(word in text for word in ['penghasilan', 'income', 'gaji']):
            return 'service_penghasilan'
        
        elif any(word in text for word in ['data', 'cari', 'search', 'temukan', 'cek']):
            return 'check_data'
        
        elif any(word in text for word in ['semua data', 'tampilkan data', 'list data', 'daftar']):
            return 'show_all_data'
        
        elif any(word in text for word in ['reset', 'bersihkan', 'clear', 'hapus']):
            return 'reset_input'
        
        elif any(word in text for word in ['keluar', 'exit', 'tutup', 'matikan']):
            return 'exit_application'
        
        # Percakapan umum
        if self.conversation_manager:
            conversation_response = self.conversation_manager.process_contextual_conversation(text)
            if conversation_response:
                return 'conversation'
        
        return None
    
    def get_command(self):
        """Get voice command dari queue"""
        try:
            return self.command_queue.get_nowait()
        except queue.Empty:
            return None
    
    def set_voice_speed(self, speed):
        """Set kecepatan suara"""
        speed_map = {
            'slow': 120,
            'normal': 150,
            'fast': 180
        }
        self.voice_speed = speed_map.get(speed, 150)
        config.set('voice_speed', self.voice_speed)
        logger.info(f"SUCCESS Voice speed set to: {speed} ({self.voice_speed})")
        
        # Berikan feedback suara
        speed_names = {
            'slow': 'lambat',
            'normal': 'normal',
            'fast': 'cepat'
        }
        self.speak(f"Kecepatan suara diatur ke {speed_names.get(speed, 'normal')}")

# =============================================================================
# ENHANCED COMPUTER VISION DENGAN FACE RECOGNITION
# =============================================================================

class EnhancedComputerVision:
    def __init__(self):
        self.face_cascade = None
        self.eye_cascade = None
        self.smile_cascade = None
        self.face_detection_enabled = config.get('face_detection_enabled', False)
        self.face_recognition = AdvancedFaceRecognition()
        self.cascade_loaded = False
        self.cascade_dir = config.get('cascade_dir')
        self.load_haar_cascades_with_fallback()
    
    def get_opencv_data_path(self):
        """Dapatkan path data OpenCV dengan kompatibilitas berbagai versi"""
        possible_paths = []
        # Coba berbagai cara untuk mendapatkan path haarcascades
        try:
            # Versi OpenCV yang memiliki cv2.data.haarcascades
            if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                possible_paths.append(cv2.data.haarcascades)
        except:
            pass
        
        # Standard installation paths
        possible_paths.extend([
            '/usr/share/opencv4/haarcascades/',
            '/usr/local/share/opencv4/haarcascades/',
            '/usr/share/opencv/haarcascades/',
            '/usr/local/share/opencv/haarcascades/',
            '/opt/opencv/data/haarcascades/',
            # Windows paths
            'C:/opencv/build/etc/haarcascades/',
            'C:/opencv/sources/data/haarcascades/',
            # Local directory
            './cascade_files/',
            './',
            self.cascade_dir
        ])
        
        # Filter hanya path yang valid
        valid_paths = []
        for path in possible_paths:
            if path and os.path.exists(path):
                valid_paths.append(path)
                logger.info(f"INFO Found OpenCV data path: {path}")
        
        return valid_paths
    
    def download_cascade_files(self):
        """Download cascade files jika tidak ada (fallback)"""
        cascade_urls = {
            'haarcascade_frontalface_default.xml': 'https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml',
            'haarcascade_eye.xml': 'https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml',
            'haarcascade_smile.xml': 'https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_smile.xml'
        }
        
        for cascade_name, url in cascade_urls.items():
            cascade_path = os.path.join(self.cascade_dir, cascade_name)
            if not os.path.exists(cascade_path):
                try:
                    logger.info(f"DOWNLOAD Downloading {cascade_name}...")
                    os.makedirs(self.cascade_dir, exist_ok=True)
                    urllib.request.urlretrieve(url, cascade_path)
                    logger.info(f"SUCCESS Downloaded: {cascade_name}")
                except Exception as e:
                    logger.error(f"ERROR Failed to download {cascade_name}: {e}")
    
    def load_haar_cascades_with_fallback(self):
        """Load Haar Cascades dengan multiple fallback methods"""
        cascade_files = {
            'face': 'haarcascade_frontalface_default.xml',
            'eye': 'haarcascade_eye.xml', 
            'smile': 'haarcascade_smile.xml'
        }
        
        # Download cascade files jika diperlukan
        self.download_cascade_files()
        
        # Dapatkan semua kemungkinan path
        possible_paths = self.get_opencv_data_path()
        
        successful_loads = 0
        
        for cascade_type, cascade_file in cascade_files.items():
            cascade_loaded = False
            
            for base_path in possible_paths:
                if base_path is None:
                    continue
                
                cascade_path = os.path.join(base_path, cascade_file)
                if os.path.exists(cascade_path):
                    try:
                        cascade_classifier = cv2.CascadeClassifier(cascade_path)
                        if cascade_classifier.empty():
                            logger.warning(f"WARNING Cascade file exists but is empty: {cascade_path}")
                            continue
                        
                        if cascade_type == 'face':
                            self.face_cascade = cascade_classifier
                            cascade_loaded = True
                            successful_loads += 1
                            logger.info(f"SUCCESS Loaded face cascade: {cascade_path}")
                            break
                        elif cascade_type == 'eye':
                            self.eye_cascade = cascade_classifier
                            cascade_loaded = True
                            successful_loads += 1
                            logger.info(f"SUCCESS Loaded eye cascade: {cascade_path}")
                            break
                        elif cascade_type == 'smile':
                            self.smile_cascade = cascade_classifier
                            cascade_loaded = True
                            successful_loads += 1
                            logger.info(f"SUCCESS Loaded smile cascade: {cascade_path}")
                            break
                    except Exception as e:
                        logger.error(f"ERROR Error loading {cascade_path}: {e}")
                        continue
            
            if not cascade_loaded:
                logger.warning(f"WARNING Could not load {cascade_file} from any known location")
        
        # Final check
        if successful_loads > 0:
            self.cascade_loaded = True
            logger.info(f"SUCCESS Computer Vision: READY ({successful_loads}/3 cascades loaded)")
        else:
            self.cascade_loaded = False
            logger.error("ERROR Computer Vision: UNAVAILABLE - No cascade files could be loaded")
    
    def enable_face_detection(self):
        """Enable deteksi wajah"""
        if not self.cascade_loaded:
            logger.error("ERROR Face Detection: UNAVAILABLE - Cascade not loaded")
            return False
        
        self.face_detection_enabled = True
        config.set('face_detection_enabled', True)
        logger.info("SUCCESS Face Detection: ENABLED")
        return True
    
    def disable_face_detection(self):
        """Disable deteksi wajah"""
        self.face_detection_enabled = False
        config.set('face_detection_enabled', False)
        logger.info("SUCCESS Face Detection: DISABLED")
        return True
    
    def enable_face_recognition(self):
        """Enable face recognition"""
        if not self.face_recognition.recognition_enabled:
            logger.warning("WARNING Face recognition not available")
            return False
        
        self.face_recognition.recognition_enabled = True
        config.set('face_recognition_enabled', True)
        logger.info("SUCCESS Face Recognition: ENABLED")
        return True
    
    def disable_face_recognition(self):
        """Disable face recognition"""
        self.face_recognition.recognition_enabled = False
        config.set('face_recognition_enabled', False)
        logger.info("SUCCESS Face Recognition: DISABLED")
        return True
    
    def register_current_face(self, person_name, frame=None):
        """Daftarkan wajah yang sedang terdeteksi"""
        if not self.face_detection_enabled:
            logger.error("ERROR Face detection not enabled")
            return None
        
        try:
            # Jika frame tidak disediakan, gunakan frame dummy
            if frame is None:
                if CV2_AVAILABLE:
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                else:
                    logger.warning("WARNING No frame provided and OpenCV not available")
                    return None
            
            # Deteksi wajah dalam frame
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame.copy()
            
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            if len(faces) == 0:
                logger.warning("WARNING No face detected in frame")
                return None
            
            # Ambil wajah pertama
            (x, y, w, h) = faces[0]
            face_roi = frame[y:y+h, x:x+w]
            
            # Daftarkan wajah
            face_id = self.face_recognition.register_face(face_roi, person_name)
            
            if face_id:
                logger.info(f"SUCCESS Face registered for {person_name} with ID: {face_id}")
                return face_id
            else:
                logger.error("ERROR Failed to register face")
                return None
                
        except Exception as e:
            logger.error(f"ERROR Face registration error: {e}")
            traceback.print_exc()
            return None
    
    def detect_faces(self, frame):
        """Deteksi dan recognize wajah dalam frame"""
        if not self.face_detection_enabled or not self.cascade_loaded:
            if isinstance(frame, Image.Image):
                return frame, 0, []
            
            if isinstance(frame, np.ndarray):
                if len(frame.shape) == 3:
                    return frame.copy(), 0, []
                else:
                    # Convert grayscale to BGR
                    return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), 0, []
            
            return frame, 0, []
        
        try:
            # Convert ke format yang sesuai
            if isinstance(frame, Image.Image):
                frame_cv = np.array(frame)
                if len(frame_cv.shape) == 3:
                    frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_RGB2BGR)
                else:
                    frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_GRAY2BGR)
            else:
                frame_cv = frame.copy()
                if len(frame_cv.shape) == 2:  # Grayscale
                    frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_GRAY2BGR)
            
            recognized_faces = []
            face_count = 0
            
            # Jika face recognition aktif
            if self.face_recognition.recognition_enabled:
                processed_frame, recognized_faces = self.face_recognition.detect_and_recognize_faces(frame_cv)
                face_count = len(recognized_faces)
            else:
                # Hanya deteksi wajah biasa
                gray = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30)
                )
                face_count = len(faces)
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame_cv, (x, y), (x+w, y+h), (0, 165, 255), 2)  # Orange color
                    cv2.putText(frame_cv, 'WAJAH', (x, y-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            
            # Convert back to original format
            if isinstance(frame, Image.Image):
                frame_cv = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
                return Image.fromarray(frame_cv), face_count, recognized_faces
            else:
                return frame_cv, face_count, recognized_faces
                
        except Exception as e:
            logger.error(f"ERROR Face detection error: {e}")
            traceback.print_exc()
            return frame, 0, []

# =============================================================================
# FIXED CAMERA SYSTEM DENGAN ENHANCED COMPUTER VISION
# =============================================================================

class AdvancedCameraSystem:
    def __init__(self):
        self.camera_available = PICAMERA2_AVAILABLE or CV2_AVAILABLE
        self.camera = None
        self.is_active = False
        self.foto_dir = config.get('photo_dir')
        self.computer_vision = EnhancedComputerVision()
        self.current_frame = None  # Menyimpan frame terakhir
        self.preview_fps = config.get('preview_fps', 10)
        self.last_frame_time = 0
        self.frame_lock = threading.Lock()
        
        # Buat direktori foto jika belum ada
        os.makedirs(self.foto_dir, exist_ok=True)
        logger.info(f"SUCCESS Foto akan disimpan di: {self.foto_dir}")
        
        if self.camera_available:
            try:
                if PICAMERA2_AVAILABLE:
                    self.camera = Picamera2()
                    config_camera = self.camera.create_preview_configuration(
                        main={"size": (640, 480), "format": "RGB888"},
                        controls={"FrameRate": self.preview_fps}
                    )
                    self.camera.configure(config_camera)
                    logger.info("SUCCESS Camera System: PICAMERA2 READY")
                else:
                    # Untuk OpenCV
                    camera_index = 0  # Default camera
                    self.camera = cv2.VideoCapture(camera_index)
                    
                    # Coba set resolution
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.camera.set(cv2.CAP_PROP_FPS, self.preview_fps)
                    
                    # Test camera
                    ret, test_frame = self.camera.read()
                    if not ret or test_frame is None:
                        logger.error("ERROR Camera test failed")
                        self.camera_available = False
                    else:
                        logger.info("SUCCESS Camera System: OPENCV READY")
            except Exception as e:
                logger.error(f"ERROR Camera System: UNAVAILABLE - {e}")
                self.camera_available = False
        else:
            logger.info("INFO Camera System: SIMULATION MODE")
    
    def enable_face_detection(self):
        """Enable face detection melalui computer vision"""
        return self.computer_vision.enable_face_detection()
    
    def disable_face_detection(self):
        """Disable face detection"""
        return self.computer_vision.disable_face_detection()
    
    def enable_face_recognition(self):
        """Enable face recognition"""
        return self.computer_vision.enable_face_recognition()
    
    def disable_face_recognition(self):
        """Disable face recognition"""
        return self.computer_vision.disable_face_recognition()
    
    def register_face(self, person_name):
        """Daftarkan wajah"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.computer_vision.register_current_face(person_name, self.current_frame)
            else:
                logger.warning("WARNING No current frame available for face registration")
                return None
    
    def is_face_detection_enabled(self):
        """Check jika face detection aktif"""
        return self.computer_vision.face_detection_enabled
    
    def is_face_recognition_enabled(self):
        """Check jika face recognition aktif"""
        return self.computer_vision.face_recognition.recognition_enabled
    
    def start_preview(self):
        """Mulai preview kamera"""
        if not self.camera_available:
            self.is_active = True
            logger.info("SUCCESS Camera preview: STARTED (SIMULATION MODE)")
            return True
        
        try:
            if PICAMERA2_AVAILABLE:
                self.camera.start()
            self.is_active = True
            logger.info("SUCCESS Camera preview: STARTED")
            return True
        except Exception as e:
            logger.error(f"ERROR Camera start failed: {e}")
            return False
    
    def stop_preview(self):
        """Stop preview kamera"""
        if not self.camera_available:
            self.is_active = False
            logger.info("SUCCESS Camera preview: STOPPED (SIMULATION MODE)")
            return True
        
        try:
            if PICAMERA2_AVAILABLE:
                self.camera.stop()
            self.is_active = False
            logger.info("SUCCESS Camera preview: STOPPED")
            return True
        except Exception as e:
            logger.error(f"ERROR Camera stop failed: {e}")
            return False
    
    def get_frame(self):
        """Dapatkan frame dengan computer vision processing - Return PIL Image"""
        if not self.is_active:
            return None
        
        try:
            current_time = time.time()
            # Batasi frame rate
            if current_time - self.last_frame_time < 1.0 / self.preview_fps:
                return self.current_frame
            
            self.last_frame_time = current_time
            
            if self.camera_available:
                if PICAMERA2_AVAILABLE and self.camera:
                    # Get frame dari Picamera2
                    frame_array = self.camera.capture_array()
                    if frame_array is not None:
                        with self.frame_lock:
                            self.current_frame = frame_array.copy()
                        
                        # Process dengan computer vision jika aktif
                        if (self.computer_vision.face_detection_enabled or 
                            self.computer_vision.face_recognition.recognition_enabled):
                            processed_frame, face_count, recognized_faces = self.computer_vision.detect_faces(frame_array)
                            if isinstance(processed_frame, np.ndarray):
                                # Convert BGR to RGB for PIL
                                if len(processed_frame.shape) == 3 and processed_frame.shape[2] == 3:
                                    processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                return Image.fromarray(processed_frame)
                            else:
                                return processed_frame
                        else:
                            # Convert langsung ke PIL Image
                            return Image.fromarray(frame_array)
                
                elif CV2_AVAILABLE and self.camera:
                    # Get frame dari OpenCV
                    ret, frame = self.camera.read()
                    if ret and frame is not None:
                        with self.frame_lock:
                            self.current_frame = frame.copy()
                        
                        # Process dengan computer vision jika aktif
                        if (self.computer_vision.face_detection_enabled or 
                            self.computer_vision.face_recognition.recognition_enabled):
                            processed_frame, face_count, recognized_faces = self.computer_vision.detect_faces(frame)
                            if isinstance(processed_frame, np.ndarray):
                                # Convert BGR to RGB for PIL
                                processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                                return Image.fromarray(processed_frame)
                            else:
                                return processed_frame
                        else:
                            # Convert BGR to RGB untuk PIL
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            return Image.fromarray(frame_rgb)
                    else:
                        logger.warning("WARNING Empty frame from camera")
                        return self.create_simulation_frame()
            else:
                # Create simulated frame dengan computer vision
                return self.create_simulation_frame()
            
            return None
            
        except Exception as e:
            logger.error(f"ERROR Frame capture error: {e}")
            traceback.print_exc()
            return self.create_simulation_frame()
    
    def capture_image(self, filename=None):
        """Capture gambar dari kamera"""
        if not self.is_active:
            logger.error("ERROR Camera not active")
            return None
        
        try:
            # Buat nama file dengan timestamp jika tidak diberikan
            if filename is None:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"foto_penduduk_{timestamp}.jpg"
            
            # Pastikan path lengkap ke direktori foto
            filepath = os.path.join(self.foto_dir, filename)
            
            if self.camera_available:
                if PICAMERA2_AVAILABLE:
                    # Capture langsung ke file
                    request = self.camera.capture_request()
                    request.save("main", filepath)
                    request.release()
                    logger.info(f"SUCCESS Photo saved (Picamera2): {filepath}")
                    return filepath
                else:
                    ret, frame = self.camera.read()
                    if ret and frame is not None:
                        # Process dengan computer vision jika aktif
                        if (self.computer_vision.face_detection_enabled or 
                            self.computer_vision.face_recognition.recognition_enabled):
                            processed_frame, face_count, recognized_faces = self.computer_vision.detect_faces(frame)
                            cv2.imwrite(filepath, processed_frame)
                        else:
                            cv2.imwrite(filepath, frame)
                        logger.info(f"SUCCESS Photo saved (OpenCV): {filepath}")
                        return filepath
                    else:
                        logger.error("ERROR Failed to capture frame from OpenCV camera")
                        return None
            else:
                # Create simulated photo
                img = self.create_simulation_frame()
                if isinstance(img, Image.Image):
                    img.save(filepath, quality=95)
                    logger.info(f"SUCCESS Simulated photo saved: {filepath}")
                    return filepath
                else:
                    logger.error("ERROR Failed to create simulated photo")
                    return None
        
        except Exception as e:
            logger.error(f"ERROR Capture error: {e}")
            traceback.print_exc()
            return None
    
    def create_simulation_frame(self):
        """Buat frame simulasi untuk fallback"""
        try:
            img = Image.new('RGB', (640, 480), color='lightblue')
            draw = ImageDraw.Draw(img)
            
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 20)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                except:
                    font = ImageFont.load_default()
            
            # Jika face detection aktif, tambahkan simulasi wajah
            if self.computer_vision.face_detection_enabled:
                draw.rectangle([160, 120, 480, 360], outline='green', width=3)
                draw.text((320, 100), "SIMULATED FACE", fill='green', font=font, anchor='mm')
            
            draw.text((320, 240), "CAMERA PREVIEW", fill='black', font=font, anchor='mm')
            draw.text((320, 280), "(SIMULATION MODE)", fill='black', font=font, anchor='mm')
            draw.text((320, 320), f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}", 
                     fill='black', font=font, anchor='mm')
            
            return img
        except Exception as e:
            logger.error(f"ERROR Creating simulation frame: {e}")
            # Return minimal fallback image
            return Image.new('RGB', (640, 480), color='gray')
    
    def cleanup(self):
        """Cleanup camera resources dengan penanganan error yang lebih baik"""
        logger.info("CLEANUP Starting camera cleanup...")
        
        try:
            self.stop_preview()
            
            if not PICAMERA2_AVAILABLE and CV2_AVAILABLE and hasattr(self, 'camera') and self.camera is not None:
                try:
                    self.camera.release()
                except Exception as e:
                    logger.error(f"ERROR Camera release error: {e}")
            
            # Tutup semua window OpenCV
            try:
                cv2.destroyAllWindows()
            except:
                pass
            
            logger.info("SUCCESS Camera cleanup completed")
        except Exception as e:
            logger.error(f"ERROR Camera cleanup error: {e}")

# =============================================================================
# MAIN ENHANCED ROBOT APPLICATION DENGAN FITUR BARU
# =============================================================================

class AdvancedRobotDesaApp:
    def __init__(self, root):
        self.root = root
        self.user_id = f"user_{int(time.time())}"  # Generate unique user ID
        self.exit_confirmed = False
        
        # Initialize advanced components
        self.db = DatabaseManager()
        self.backup_system = BackupSystem()
        self.voice = AdvancedVoiceSystem()
        self.servo = ServoController()
        self.ocr = OCRSystem()
        self.weather = WeatherService()
        
        # Advanced camera system dengan face recognition
        self.camera = AdvancedCameraSystem()
        
        # Gamification system
        self.gamification = GamificationSystem()
        
        # Enhanced conversation manager
        self.conversation = EnhancedConversationManager(self.voice, self.db)
        self.voice.set_conversation_manager(self.conversation)
        
        self.camera_active = False
        self.preview_updating = False
        self.face_detection_enabled = config.get('face_detection_enabled', False)
        self.face_recognition_enabled = config.get('face_recognition_enabled', False)
        self.wake_word_enabled = config.get('wake_word_enabled', True)
        self.continuous_listening_enabled = config.get('continuous_listening', False)
        self.resource_monitor_thread = None
        self.system_status = {}
        
        # Setup UI
        self.setup_advanced_ui()
        
        # Register cleanup
        atexit.register(self.advanced_cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Start advanced services
        self.start_advanced_services()
        
        # Start resource monitoring
        self.start_resource_monitoring()
        
        # Unlock achievement pertama
        self.root.after(2000, lambda: self.gamification.unlock_achievement(self.user_id, 'first_use'))
        
        # Ucapan selamat datang otomatis
        self.root.after(3000, self.advanced_auto_welcome)
    
    def setup_advanced_ui(self):
        """Setup UI dengan fitur advanced voice dan face recognition"""
        self.root.title("OJAN PELAYAN DESA - VERSION 5.0 (ADVANCED & STABLE)")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#2c3e50')
        
        # Bind Esc key untuk exit
        self.root.bind('<Escape>', self.confirm_exit)
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header dengan info system
        header_frame = tk.Frame(main_frame, bg='#34495e')
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title = tk.Label(header_frame, text="OJAN PELAYAN DESA - VERSION 5.0 (ADVANCED & STABLE)", 
                        font=('Arial', 16, 'bold'), fg='white', bg='#34495e')
        title.pack(pady=10)
        
        # System info
        info_text = f"SUCCESS Wake Word: {'ON' if self.wake_word_enabled else 'OFF'} | " \
                   f"Face Rec: {'ON' if self.face_recognition_enabled else 'OFF'} | " \
                   f"Continuous: {'ON' if self.continuous_listening_enabled else 'OFF'}"
        self.info_label = tk.Label(header_frame, text=info_text, font=('Arial', 9), 
                             fg='#ecf0f1', bg='#34495e')
        self.info_label.pack(pady=5)
        
        # Content area
        content_frame = tk.Frame(main_frame, bg='#2c3e50')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Controls
        left_frame = tk.LabelFrame(content_frame, text=" KONTROL & LAYANAN", 
                                 font=('Arial', 12, 'bold'), bg='#ecf0f1', padx=10, pady=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))
        
        # Middle panel - Advanced Features
        middle_frame = tk.LabelFrame(content_frame, text=" FITUR ADVANCED", 
                                   font=('Arial', 12, 'bold'), bg='#ecf0f1', padx=10, pady=10)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        
        # Right panel - Camera & Analytics
        right_frame = tk.LabelFrame(content_frame, text=" KAMERA & FACE RECOGNITION", 
                                  font=('Arial', 12, 'bold'), bg='#ecf0f1', padx=10, pady=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # ===== LEFT PANEL CONTENT =====
        self.setup_left_panel(left_frame)
        
        # ===== MIDDLE PANEL CONTENT =====
        self.setup_middle_panel_advanced(middle_frame)
        
        # ===== RIGHT PANEL CONTENT =====
        self.setup_right_panel_advanced(right_frame)
        
        # ===== STATUS BAR ADVANCED =====
        self.setup_advanced_status_bar(main_frame)
    
    def setup_left_panel(self, parent):
        """Setup left panel dengan kontrol dasar"""
        # NIK Input
        input_frame = tk.Frame(parent, bg='#ecf0f1')
        input_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(input_frame, text="NIK (16 digit):", 
                font=('Arial', 11, 'bold'), bg='#ecf0f1').pack()
        
        self.nik_entry = tk.Entry(input_frame, font=('Arial', 14), width=20, justify='center')
        self.nik_entry.pack(pady=5)
        
        # Reset button
        reset_btn = tk.Button(input_frame, text="RESET INPUT", 
                            command=self.reset_input, font=('Arial', 10),
                            bg='#95a5a6', fg='white', relief=tk.RAISED)
        reset_btn.pack(pady=5)
        
        # Service buttons
        services_frame = tk.Frame(parent, bg='#ecf0f1')
        services_frame.pack(fill=tk.X, pady=10)
        
        services = [
            ("BUAT SKTM", "SKTM"),
            ("BUAT DOMISILI", "DOMISILI"), 
            ("BUAT USAHA", "USAHA"),
            ("SURAT PENGHASILAN", "PENGHASILAN"),
            ("CEK DATA", "CEK_DATA"),
            ("SEMUA DATA", "SHOW_ALL_DATA")
        ]
        
        for i, (text, command) in enumerate(services):
            btn = tk.Button(services_frame, text=text, font=('Arial', 9),
                          command=lambda cmd=command: self.handle_service(cmd),
                          bg='#3498db', fg='white', height=2, width=18,
                          relief=tk.RAISED, activebackground='#2980b9')
            btn.grid(row=i//2, column=i%2, padx=2, pady=2, sticky='ew')
        
        # Tombol tambah data warga
        add_warga_btn = tk.Button(parent, text="TAMBAH DATA WARGA", 
                                command=self.add_warga_dialog, font=('Arial', 11, 'bold'),
                                bg='#27ae60', fg='white', height=2)
        add_warga_btn.pack(fill=tk.X, pady=10)
        
        # Servo controls
        servo_frame = tk.LabelFrame(parent, text=" KONTROL SERVO", 
                                  font=('Arial', 11, 'bold'), bg='#ecf0f1', pady=5)
        servo_frame.pack(fill=tk.X, pady=10)
        
        servo_buttons = [
            ("LAMBAI TANGAN", self.servo.wave_hand),
            ("ANGGUK KEPALA", self.servo.nod_head),
            ("RESET SERVO", self.servo.reset_all_servos)
        ]
        
        for i, (text, command) in enumerate(servo_buttons):
            btn = tk.Button(servo_frame, text=text, font=('Arial', 10),
                          command=command, bg='#9b59b6', fg='white', height=1, width=15,
                          relief=tk.RAISED, activebackground='#8e44ad')
            btn.pack(pady=2)
        
        # OCR button
        ocr_btn = tk.Button(parent, text="SCAN NIK (OCR)", 
                          command=self.scan_document, font=('Arial', 11, 'bold'),
                          bg='#e67e22', fg='white', height=2,
                          relief=tk.RAISED, activebackground='#d35400')
        ocr_btn.pack(fill=tk.X, pady=10)
        
        # Voice commands help
        help_btn = tk.Button(parent, text="BANTUAN PERINTAH SUARA", 
                           command=self.show_voice_help, font=('Arial', 10),
                           bg='#2ecc71', fg='white', height=1,
                           relief=tk.RAISED, activebackground='#27ae60')
        help_btn.pack(fill=tk.X, pady=5)
    
    def setup_middle_panel_advanced(self, parent):
        """Setup middle panel dengan fitur advanced"""
        # Advanced Voice Controls
        voice_frame = tk.LabelFrame(parent, text=" ADVANCED VOICE CONTROL", 
                                  font=('Arial', 11, 'bold'), bg='#ecf0f1')
        voice_frame.pack(fill=tk.X, pady=5)
        
        wake_word_btn = tk.Button(voice_frame, text="TOGGLE WAKE WORD",
                                command=self.toggle_wake_word, font=('Arial', 10),
                                bg='#3498db', fg='white', relief=tk.RAISED,
                                activebackground='#2980b9')
        wake_word_btn.pack(fill=tk.X, pady=2)
        
        continuous_btn = tk.Button(voice_frame, text="TOGGLE CONTINUOUS LISTENING",
                                 command=self.toggle_continuous_listening, font=('Arial', 10),
                                 bg='#9b59b6', fg='white', relief=tk.RAISED,
                                 activebackground='#8e44ad')
        continuous_btn.pack(fill=tk.X, pady=2)
        
        # Voice speed controls
        speed_frame = tk.Frame(voice_frame, bg='#ecf0f1')
        speed_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(speed_frame, text="Kecepatan Suara:", 
                font=('Arial', 9, 'bold'), bg='#ecf0f1').pack()
        
        speed_buttons_frame = tk.Frame(speed_frame, bg='#ecf0f1')
        speed_buttons_frame.pack(pady=2)
        
        speed_buttons = [
            ("Lambat", 'slow'),
            ("Normal", 'normal'),
            ("Cepat", 'fast')
        ]
        
        for text, speed in speed_buttons:
            btn = tk.Button(speed_buttons_frame, text=text, font=('Arial', 8),
                          command=lambda s=speed: self.set_voice_speed(s),
                          bg='#e67e22', fg='white', width=8,
                          relief=tk.RAISED, activebackground='#d35400')
            btn.pack(side=tk.LEFT, padx=2)
        
        # Status voice features
        self.wake_word_status = tk.Label(voice_frame, text=f"Wake Word: {'AKTIF' if self.wake_word_enabled else 'NONAKTIF'}", 
                                       font=('Arial', 9), bg='#ecf0f1', 
                                       fg='#27ae60' if self.wake_word_enabled else '#e74c3c')
        self.wake_word_status.pack(pady=2)
        
        self.continuous_status = tk.Label(voice_frame, text=f"Continuous: {'AKTIF' if self.continuous_listening_enabled else 'NONAKTIF'}", 
                                        font=('Arial', 9), bg='#ecf0f1',
                                        fg='#27ae60' if self.continuous_listening_enabled else '#e74c3c')
        self.continuous_status.pack(pady=2)
        
        # Face Recognition Controls
        face_frame = tk.LabelFrame(parent, text=" FACE RECOGNITION", 
                                 font=('Arial', 11, 'bold'), bg='#ecf0f1')
        face_frame.pack(fill=tk.X, pady=5)
        
        face_recog_btn = tk.Button(face_frame, text="TOGGLE FACE RECOGNITION",
                                 command=self.toggle_face_recognition, font=('Arial', 10),
                                 bg='#e74c3c', fg='white', relief=tk.RAISED,
                                 activebackground='#c0392b')
        face_recog_btn.pack(fill=tk.X, pady=2)
        
        register_face_btn = tk.Button(face_frame, text="REGISTER FACE",
                                    command=self.register_face_dialog, font=('Arial', 10),
                                    bg='#f39c12', fg='white', relief=tk.RAISED,
                                    activebackground='#e67e22')
        register_face_btn.pack(fill=tk.X, pady=2)
        
        self.face_recog_status = tk.Label(face_frame, text=f"Face Recognition: {'AKTIF' if self.face_recognition_enabled else 'NONAKTIF'}", 
                                        font=('Arial', 9), bg='#ecf0f1',
                                        fg='#27ae60' if self.face_recognition_enabled else '#e74c3c')
        self.face_recog_status.pack(pady=2)
        
        # Computer Vision Controls
        cv_frame = tk.LabelFrame(parent, text=" COMPUTER VISION", 
                               font=('Arial', 11, 'bold'), bg='#ecf0f1')
        cv_frame.pack(fill=tk.X, pady=5)
        
        face_detect_btn = tk.Button(cv_frame, text="TOGGLE FACE DETECTION",
                                  command=self.toggle_face_detection, font=('Arial', 10),
                                  bg='#e74c3c', fg='white', relief=tk.RAISED,
                                  activebackground='#c0392b')
        face_detect_btn.pack(fill=tk.X, pady=2)
        
        self.face_detect_status = tk.Label(cv_frame, text=f"Face Detection: {'AKTIF' if self.face_detection_enabled else 'NONAKTIF'}", 
                                         font=('Arial', 9), bg='#ecf0f1',
                                         fg='#27ae60' if self.face_detection_enabled else '#e74c3c')
        self.face_detect_status.pack(pady=2)
        
        # Gamification System
        game_frame = tk.LabelFrame(parent, text=" ACHIEVEMENT SYSTEM", 
                                 font=('Arial', 11, 'bold'), bg='#ecf0f1')
        game_frame.pack(fill=tk.X, pady=5)
        
        achievement_btn = tk.Button(game_frame, text="LIHAT ACHIEVEMENTS",
                                  command=self.show_achievements, font=('Arial', 10),
                                  bg='#f39c12', fg='white', relief=tk.RAISED,
                                  activebackground='#e67e22')
        achievement_btn.pack(fill=tk.X, pady=2)
        
        leaderboard_btn = tk.Button(game_frame, text="LIHAT LEADERBOARD",
                                  command=self.show_leaderboard, font=('Arial', 10),
                                  bg='#9b59b6', fg='white', relief=tk.RAISED,
                                  activebackground='#8e44ad')
        leaderboard_btn.pack(fill=tk.X, pady=2)
        
        # User Stats
        stats_frame = tk.LabelFrame(parent, text=" STATISTIK ANDA", 
                                  font=('Arial', 11, 'bold'), bg='#ecf0f1')
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_label = tk.Label(stats_frame, text="Memuat...", 
                                  font=('Arial', 9), bg='#ecf0f1', justify=tk.LEFT)
        self.stats_label.pack(pady=5)
    
    def setup_right_panel_advanced(self, parent):
        """Setup right panel dengan fitur face recognition"""
        # Camera preview
        self.camera_canvas = tk.Canvas(parent, bg='black', width=640, height=480,
                                     highlightthickness=2, highlightbackground='#34495e')
        self.camera_canvas.pack(pady=10)
        
        # Camera controls dengan fitur advanced
        cam_controls_frame = tk.Frame(parent, bg='#ecf0f1')
        cam_controls_frame.pack(fill=tk.X, pady=10)
        
        self.cam_btn = tk.Button(cam_controls_frame, text="START PREVIEW",
                               command=self.toggle_camera_preview,
                               font=('Arial', 11, 'bold'),
                               bg='#27ae60', fg='white', width=15, height=1,
                               relief=tk.RAISED, activebackground='#219653')
        self.cam_btn.pack(side=tk.LEFT, padx=5)
        
        self.capture_btn = tk.Button(cam_controls_frame, text="AMBIL FOTO",
                                   command=self.capture_photo,
                                   font=('Arial', 11, 'bold'),
                                   bg='#e74c3c', fg='white', width=15, height=1,
                                   relief=tk.RAISED, activebackground='#c0392b')
        self.capture_btn.pack(side=tk.LEFT, padx=5)
        
        self.capture_btn.config(state=tk.DISABLED)
        
        # Camera status dengan info advanced
        self.camera_status = tk.Label(cam_controls_frame, 
                                    text="Kamera siap | Wake Word: ON | Face Rec: OFF",
                                    font=('Arial', 8), bg='#ecf0f1', fg='#27ae60')
        self.camera_status.pack(side=tk.LEFT, padx=10)
        
        # System Info
        system_info_frame = tk.Frame(parent, bg='#ecf0f1')
        system_info_frame.pack(fill=tk.X, pady=5)
        
        system_info_text = (
            "Advanced Features Ready\n"
            f"Wake Word: {'Aktif - Katakan \'Ojan\'' if self.wake_word_enabled else 'Nonaktif'}\n"
            f"Face Recognition: {'Aktif' if self.face_recognition_enabled else 'Nonaktif'}\n"
            f"Continuous: {'Aktif' if self.continuous_listening_enabled else 'Nonaktif'}"
        )
        
        self.system_info = tk.Label(system_info_frame, 
                                  text=system_info_text,
                                  font=('Arial', 9), bg='#ecf0f1', fg='#2c3e50', 
                                  justify=tk.LEFT)
        self.system_info.pack()
        
        # Conversation display
        self.conversation_text = scrolledtext.ScrolledText(parent, height=6, width=70, 
                                       font=('Arial', 10), bg='#f8f9fa', fg='#2c3e50')
        self.conversation_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.conversation_text.insert(tk.END, "SISTEM: Sistem Advanced siap! Fitur canggih telah diaktifkan.\n")
        self.conversation_text.insert(tk.END, "INFO: Katakan 'Ojan' untuk membangunkan saya!\n")
        self.conversation_text.config(state=tk.DISABLED)
    
    def setup_advanced_status_bar(self, parent):
        """Setup status bar dengan info tambahan advanced"""
        status_frame = tk.Frame(parent, bg='#34495e', height=40)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        status_frame.pack_propagate(False)
        
        # Status info
        self.status_label = tk.Label(status_frame, text="Sistem Advanced sedang dimulai...",
                                   font=('Arial', 11), fg='white', bg='#34495e')
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, padx=20, pady=5)
        
        # Feature info
        self.feature_status = tk.Label(status_frame, text=f"Wake Word: {'ON' if self.wake_word_enabled else 'OFF'} | Face Rec: {'ON' if self.face_recognition_enabled else 'OFF'}", 
                                     font=('Arial', 9), fg='#ecf0f1', bg='#34495e')
        self.feature_status.pack(side=tk.LEFT, padx=10)
        
        # Achievement info
        self.achievement_status = tk.Label(status_frame, text="Achievements: 0 | Points: 0", 
                                         font=('Arial', 9), fg='#ecf0f1', bg='#34495e')
        self.achievement_status.pack(side=tk.RIGHT, padx=10)
        
        # Exit button
        exit_btn = tk.Button(status_frame, text="KELUAR (ESC)",
                           command=self.confirm_exit, font=('Arial', 9),
                           bg='#95a5a6', fg='white', relief=tk.RAISED,
                           activebackground='#7f8c8d')
        exit_btn.pack(side=tk.RIGHT, padx=10)
    
    def start_resource_monitoring(self):
        """Mulai monitoring resource sistem"""
        def monitor_resources():
            while getattr(self, 'monitoring_active', True):
                try:
                    # CPU usage
                    cpu_usage = subprocess.check_output(['top', '-bn1']).decode('utf-8')
                    cpu_line = [line for line in cpu_usage.split('\n') if 'Cpu(s)' in line][0]
                    cpu_percent = float(cpu_line.split()[1].replace(',', '.'))
                    
                    # Memory usage
                    mem_usage = subprocess.check_output(['free', '-m']).decode('utf-8')
                    mem_lines = mem_usage.strip().split('\n')
                    mem_values = mem_lines[1].split()
                    total_mem = int(mem_values[1])
                    used_mem = int(mem_values[2])
                    mem_percent = (used_mem / total_mem) * 100
                    
                    # Update status
                    self.system_status = {
                        'cpu': cpu_percent,
                        'memory': mem_percent
                    }
                    
                    # Log jika resource usage tinggi
                    if cpu_percent > 90 or mem_percent > 90:
                        logger.warning(f"WARNING High resource usage - CPU: {cpu_percent:.1f}%, Memory: {mem_percent:.1f}%")
                    
                    # Update UI setiap 5 detik
                    time.sleep(5)
                except Exception as e:
                    logger.error(f"ERROR Resource monitoring error: {e}")
                    time.sleep(10)
        
        self.monitoring_active = True
        self.resource_monitor_thread = threading.Thread(target=monitor_resources, daemon=True, name="ResourceMonitor")
        self.resource_monitor_thread.start()
        logger.info("SUCCESS Resource monitoring started")
    
    def confirm_exit(self, event=None):
        """Konfirmasi sebelum exit aplikasi"""
        if self.exit_confirmed:
            self.root.quit()
            return
            
        response = messagebox.askyesno(
            "Konfirmasi Keluar",
            "Apakah Anda yakin ingin keluar dari aplikasi?",
            parent=self.root
        )
        
        if response:
            self.exit_confirmed = True
            self.root.quit()
    
    def signal_handler(self, signum, frame):
        """Handle signal interrupts"""
        logger.info(f"INFO Received signal {signum}, initiating cleanup")
        self.advanced_cleanup()
        sys.exit(0)
    
    # =========================================================================
    # ADVANCED FEATURE METHODS
    # =========================================================================
    
    def toggle_wake_word(self):
        """Toggle wake word detection"""
        if self.wake_word_enabled:
            success = self.voice.disable_wake_word()
            if success:
                self.wake_word_enabled = False
                self.wake_word_status.config(text="Wake Word: NONAKTIF", fg='#e74c3c')
                self.update_status("SUCCESS Wake word dinonaktifkan")
                self.voice.speak("Wake word telah dimatikan")
            else:
                self.update_status("ERROR Gagal menonaktifkan wake word")
        else:
            success = self.voice.enable_wake_word()
            if success:
                self.wake_word_enabled = True
                self.wake_word_status.config(text="Wake Word: AKTIF", fg='#27ae60')
                self.update_status("SUCCESS Wake word diaktifkan")
                self.voice.speak("Wake word diaktifkan. Katakan Ojan untuk membangunkan saya.")
                # Unlock achievement
                self.gamification.unlock_achievement(self.user_id, 'voice_command')
            else:
                self.update_status("ERROR Gagal mengaktifkan wake word")
        
        self.update_feature_status()
    
    def toggle_continuous_listening(self):
        """Toggle continuous listening"""
        if self.continuous_listening_enabled:
            success = self.voice.disable_continuous_listening()
            if success:
                self.continuous_listening_enabled = False
                self.continuous_status.config(text="Continuous: NONAKTIF", fg='#e74c3c')
                self.update_status("SUCCESS Continuous listening dinonaktifkan")
                self.voice.speak("Continuous listening telah dimatikan")
            else:
                self.update_status("ERROR Gagal menonaktifkan continuous listening")
        else:
            success = self.voice.enable_continuous_listening()
            if success:
                self.continuous_listening_enabled = True
                self.continuous_status.config(text="Continuous: AKTIF", fg='#27ae60')
                self.update_status("SUCCESS Continuous listening diaktifkan")
                self.voice.speak("Continuous listening diaktifkan. Saya akan mendengarkan terus.")
            else:
                self.update_status("ERROR Gagal mengaktifkan continuous listening")
        
        self.update_feature_status()
    
    def toggle_face_recognition(self):
        """Toggle face recognition"""
        if self.face_recognition_enabled:
            success = self.camera.disable_face_recognition()
            if success:
                self.face_recognition_enabled = False
                self.face_recog_status.config(text="Face Recognition: NONAKTIF", fg='#e74c3c')
                self.update_status("SUCCESS Face recognition dinonaktifkan")
                self.voice.speak("Face recognition telah dimatikan")
            else:
                self.update_status("ERROR Gagal menonaktifkan face recognition")
        else:
            success = self.camera.enable_face_recognition()
            if success:
                self.face_recognition_enabled = True
                self.face_recog_status.config(text="Face Recognition: AKTIF", fg='#27ae60')
                self.update_status("SUCCESS Face recognition diaktifkan")
                self.voice.speak("Face recognition diaktifkan")
                # Unlock achievement
                self.gamification.unlock_achievement(self.user_id, 'face_detected')
            else:
                self.update_status("ERROR Gagal mengaktifkan face recognition")
        
        self.update_feature_status()
    
    def toggle_face_detection(self):
        """Toggle face detection on/off"""
        if self.face_detection_enabled:
            success = self.camera.disable_face_detection()
            if success:
                self.face_detection_enabled = False
                self.face_detect_status.config(text="Face Detection: NONAKTIF", fg='#e74c3c')
                self.update_camera_status_text("Face Detection: OFF")
                self.update_status("SUCCESS Face detection dinonaktifkan")
                self.voice.speak("Deteksi wajah telah dimatikan")
            else:
                self.update_status("ERROR Gagal menonaktifkan face detection")
        else:
            success = self.camera.enable_face_detection()
            if success:
                self.face_detection_enabled = True
                self.face_detect_status.config(text="Face Detection: AKTIF", fg='#27ae60')
                self.update_camera_status_text("Face Detection: ON")
                self.update_status("SUCCESS Face detection diaktifkan")
                self.voice.speak("Deteksi wajah diaktifkan")
            else:
                self.update_status("ERROR Gagal mengaktifkan face detection")
    
    def set_voice_speed(self, speed):
        """Set kecepatan suara"""
        self.voice.set_voice_speed(speed)
        speed_names = {
            'slow': 'lambat',
            'normal': 'normal', 
            'fast': 'cepat'
        }
        self.update_status(f"SUCCESS Kecepatan suara diatur ke: {speed_names[speed]}")
    
    def register_face_dialog(self):
        """Dialog untuk registrasi wajah baru"""
        if not self.camera_active:
            messagebox.showwarning("Peringatan", "Aktifkan kamera terlebih dahulu!", parent=self.root)
            return
        
        if not self.face_detection_enabled:
            messagebox.showwarning("Peringatan", "Aktifkan face detection terlebih dahulu!", parent=self.root)
            return
        
        # Buat dialog input nama
        dialog = tk.Toplevel(self.root)
        dialog.title("Registrasi Wajah")
        dialog.geometry("300x150")
        dialog.configure(bg='#ecf0f1')
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Masukkan nama untuk wajah ini:", 
                font=('Arial', 12), bg='#ecf0f1').pack(pady=10)
        
        name_entry = tk.Entry(dialog, font=('Arial', 14), width=20)
        name_entry.pack(pady=5)
        name_entry.focus()
        
        def register():
            person_name = name_entry.get().strip()
            if person_name:
                dialog.destroy()
                self.update_status(f"REGISTER Mendaftarkan wajah: {person_name}...")
                self.voice.speak(f"Mendaftarkan wajah {person_name}, harap lihat kamera")
                
                def do_registration():
                    time.sleep(2)  # Beri waktu user untuk siap
                    success = self.camera.register_face(person_name)
                    if success:
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Berhasil", 
                            f"Wajah {person_name} berhasil didaftarkan!",
                            parent=self.root
                        ))
                        self.root.after(0, lambda: self.update_status(f"SUCCESS Wajah {person_name} terdaftar"))
                        self.root.after(0, lambda: self.voice.speak(f"Wajah {person_name} berhasil didaftarkan"))
                        # Unlock achievement
                        self.gamification.unlock_achievement(self.user_id, 'face_detected')
                    else:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Error", 
                            "Gagal mendaftarkan wajah. Pastikan wajah terlihat jelas di kamera.",
                            parent=self.root
                        ))
                        self.root.after(0, lambda: self.update_status("ERROR Gagal mendaftarkan wajah"))
                
                threading.Thread(target=do_registration, daemon=True).start()
            else:
                messagebox.showwarning("Peringatan", "Masukkan nama terlebih dahulu!", parent=dialog)
        
        tk.Button(dialog, text="Daftarkan", command=register,
                 font=('Arial', 11), bg='#3498db', fg='white').pack(pady=10)
        
        dialog.bind('<Return>', lambda e: register())
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def add_warga_dialog(self):
        """Dialog untuk menambah data warga baru"""
        # Buat dialog input data
        dialog = tk.Toplevel(self.root)
        dialog.title("Tambah Data Warga")
        dialog.geometry("400x400")
        dialog.configure(bg='#ecf0f1')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form fields
        fields = [
            ("NIK (16 digit)", "nik"),
            ("Nama Lengkap", "nama"),
            ("Alamat", "alamat"),
            ("Tanggal Lahir (YYYY-MM-DD)", "ttl"),
            ("Pekerjaan", "pekerjaan")
        ]
        
        entries = {}
        
        for label, field in fields:
            frame = tk.Frame(dialog, bg='#ecf0f1')
            frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(frame, text=label, font=('Arial', 10), bg='#ecf0f1').pack(anchor='w')
            entry = tk.Entry(frame, font=('Arial', 12), width=30)
            entry.pack(fill=tk.X, pady=2)
            entries[field] = entry
        
        # Fokus ke NIK field
        entries['nik'].focus()
        
        def save_warga():
            nik = entries['nik'].get().strip()
            nama = entries['nama'].get().strip()
            alamat = entries['alamat'].get().strip()
            ttl = entries['ttl'].get().strip()
            pekerjaan = entries['pekerjaan'].get().strip()
            
            # Validasi
            if not all([nik, nama, alamat, ttl, pekerjaan]):
                messagebox.showwarning("Peringatan", "Semua field harus diisi!", parent=dialog)
                return
            
            if len(nik) != 16 or not nik.isdigit():
                messagebox.showwarning("Peringatan", "NIK harus 16 digit angka!", parent=dialog)
                return
            
            # Simpan ke database
            success = self.db.add_warga(nik, nama, alamat, ttl, pekerjaan)
            if success:
                dialog.destroy()
                messagebox.showinfo("Berhasil", "Data warga berhasil ditambahkan!", parent=self.root)
                self.voice.speak("Data warga berhasil ditambahkan")
                self.update_status("SUCCESS Data warga ditambahkan")
                # Unlock achievement
                self.gamification.unlock_achievement(self.user_id, 'data_entry')
                self.gamification.add_activity_point(self.user_id, 'data_entry', 15)
            else:
                messagebox.showerror("Error", "Gagal menambahkan data warga!", parent=dialog)
        
        # Tombol simpan
        btn_frame = tk.Frame(dialog, bg='#ecf0f1')
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="SIMPAN", command=save_warga,
                 font=('Arial', 11), bg='#27ae60', fg='white', width=10).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="BATAL", command=dialog.destroy,
                 font=('Arial', 11), bg='#e74c3c', fg='white', width=10).pack(side=tk.LEFT, padx=5)
        
        dialog.bind('<Return>', lambda e: save_warga())
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def update_feature_status(self):
        """Update status fitur di status bar"""
        wake_status = "ON" if self.wake_word_enabled else "OFF"
        face_rec_status = "ON" if self.face_recognition_enabled else "OFF"
        continuous_status = "ON" if self.continuous_listening_enabled else "OFF"
        
        self.feature_status.config(
            text=f"Wake Word: {wake_status} | Face Rec: {face_rec_status} | Continuous: {continuous_status}"
        )
        
        # Update info label
        info_text = f"SUCCESS Wake Word: {wake_status} | " \
                   f"Face Rec: {face_rec_status} | " \
                   f"Continuous: {continuous_status}"
        self.info_label.config(text=info_text)
        
        # Update system info
        system_info_text = (
            "Advanced Features Ready\n"
            f"Wake Word: {'Aktif - Katakan \'Ojan\'' if self.wake_word_enabled else 'Nonaktif'}\n"
            f"Face Recognition: {'Aktif' if self.face_recognition_enabled else 'Nonaktif'}\n"
            f"Continuous: {'Aktif' if self.continuous_listening_enabled else 'Nonaktif'}"
        )
        self.system_info.config(text=system_info_text)
    
    # =========================================================================
    # IMPLEMENTASI METHOD YANG SUDAH ADA (dengan enhancements)
    # =========================================================================
    
    def start_advanced_services(self):
        """Start semua services advanced"""
        # Start backup scheduler
        self.backup_system.start_auto_backup_scheduler()
        
        # Start voice recognition dengan wake word enabled
        if self.voice.start_listening():
            logger.info("SUCCESS Advanced voice recognition aktif")
            # Enable wake word sesuai konfigurasi
            if self.wake_word_enabled:
                self.voice.enable_wake_word()
            # Start voice command processing
            self.root.after(100, self.process_advanced_voice_commands)
        
        # Start camera automatically setelah delay
        self.root.after(3000, self.initialize_camera)
        
        # Update user stats
        self.root.after(2000, self.update_user_stats_display)
        
        # Update achievement status
        self.root.after(2500, self.update_achievement_status)
    
    def process_advanced_voice_commands(self):
        """PROSES VOICE COMMANDS DENGAN FITUR ADVANCED"""
        command = self.voice.get_command()
        if command:
            logger.info(f"VOICE Advanced voice command: {command}")
            self.execute_advanced_voice_command(command)
        
        # Continue listening
        if self.voice.listening:
            self.root.after(100, self.process_advanced_voice_commands)
    
    def execute_advanced_voice_command(self, command):
        """EXECUTE VOICE COMMANDS DENGAN FITUR ADVANCED"""
        # Perintah advanced voice features
        if command == 'enable_wake_word':
            if not self.wake_word_enabled:
                self.toggle_wake_word()
        elif command == 'disable_wake_word':
            if self.wake_word_enabled:
                self.toggle_wake_word()
        elif command == 'enable_continuous_listening':
            if not self.continuous_listening_enabled:
                self.toggle_continuous_listening()
        elif command == 'disable_continuous_listening':
            if self.continuous_listening_enabled:
                self.toggle_continuous_listening()
        elif command == 'enable_face_recognition':
            if not self.face_recognition_enabled:
                self.toggle_face_recognition()
        elif command == 'disable_face_recognition':
            if self.face_recognition_enabled:
                self.toggle_face_recognition()
        elif command == 'register_face':
            self.register_face_dialog()
        elif command == 'set_voice_fast':
            self.set_voice_speed('fast')
        elif command == 'set_voice_slow':
            self.set_voice_speed('slow')
        elif command == 'set_voice_normal':
            self.set_voice_speed('normal')
        elif command == 'enable_face_detection':
            if not self.face_detection_enabled:
                self.toggle_face_detection()
        elif command == 'disable_face_detection':
            if self.face_detection_enabled:
                self.toggle_face_detection()
        # Perintah lainnya
        else:
            self.execute_enhanced_voice_command(command)
    
    def execute_enhanced_voice_command(self, command):
        """Execute perintah voice yang sudah ada"""
        if command == 'get_time':
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            self.voice.speak(f"Sekarang jam {current_time}")
            self.add_conversation(f"WAKTU: Sekarang jam {current_time}")
        
        elif command == 'get_date':
            current_date = datetime.datetime.now().strftime("%d %B %Y")
            current_day = datetime.datetime.now().strftime("%A")
            days = {
                'Monday': 'Senin',
                'Tuesday': 'Selasa', 
                'Wednesday': 'Rabu',
                'Thursday': 'Kamis',
                'Friday': 'Jumat',
                'Saturday': 'Sabtu',
                'Sunday': 'Minggu'
            }
            self.voice.speak(f"Hari ini {days.get(current_day, current_day)}, tanggal {current_date}")
            self.add_conversation(f"TANGGAL: Hari ini {days.get(current_day, current_day)}, {current_date}")
        
        elif command == 'get_weather':
            weather_info = self.weather.get_weather()
            self.voice.speak(weather_info)
            self.add_conversation(f"CUACA: {weather_info}")
        
        elif command == 'show_achievements':
            self.show_achievements()
        
        elif command == 'show_leaderboard':
            self.show_leaderboard()
        
        elif command == 'start_camera':
            if not self.camera_active:
                self.start_enhanced_camera()
        
        elif command == 'stop_camera':
            if self.camera_active:
                self.stop_enhanced_preview()
        
        elif command == 'capture_photo':
            if self.camera_active:
                self.capture_photo()
            else:
                self.voice.speak("Aktifkan kamera terlebih dahulu")
        
        elif command == 'scan_document':
            if self.camera_active:
                self.scan_document()
            else:
                self.voice.speak("Aktifkan kamera terlebih dahulu")
        
        elif command == 'wave_hand':
            self.servo.wave_hand()
            self.voice.speak("Menggerakkan tangan")
        
        elif command == 'nod_head':
            self.servo.nod_head()
            self.voice.speak("Menganggukkan kepala")
        
        elif command == 'service_sktm':
            self.handle_service("SKTM")
        
        elif command == 'service_domisili':
            self.handle_service("DOMISILI")
        
        elif command == 'service_usaha':
            self.handle_service("USAHA")
        
        elif command == 'service_penghasilan':
            self.handle_service("PENGHASILAN")
        
        elif command == 'check_data':
            self.cek_data_warga()
        
        elif command == 'show_all_data':
            self.tampilkan_semua_data()
        
        elif command == 'reset_input':
            self.reset_input()
        
        elif command == 'exit_application':
            self.confirm_exit()
        
        elif command == 'conversation':
            # Already handled by conversation manager
            pass
    
    def advanced_auto_welcome(self):
        """Ucapan selamat datang advanced"""
        self.update_status("SISTEM Advanced siap! Semua fitur canggih aktif.")
        self.add_conversation("SELAMAT DATANG: Sistem Advanced berhasil diaktifkan!")
        self.add_conversation("INFO: Katakan 'Ojan' diikuti perintah!")
        self.add_conversation("INFO: Coba aktifkan face recognition!")
        
        welcome_msg = (
            "Selamat datang! Saya Ojan versi 5.0 dengan fitur advanced yang lebih stabil. "
            f"{'Wake word aktif' if self.wake_word_enabled else 'Wake word nonaktif'}. "
            "Ada yang bisa saya bantu hari ini?"
        )
        self.voice.speak(welcome_msg)
    
    def add_conversation(self, message):
        """Tambahkan pesan ke conversation display"""
        self.conversation_text.config(state=tk.NORMAL)
        self.conversation_text.insert(tk.END, f"{message}\n")
        self.conversation_text.see(tk.END)
        self.conversation_text.config(state=tk.DISABLED)
    
    def update_status(self, message):
        """Update status message"""
        self.status_label.config(text=message)
        logger.info(f"STATUS: {message}")
    
    def update_camera_status_text(self, additional_text=""):
        """Update teks status kamera"""
        base_text = "Preview aktif" if self.camera_active else "Preview dihentikan"
        if additional_text:
            base_text += f" | {additional_text}"
        self.camera_status.config(text=base_text)
    
    def initialize_camera(self):
        """Initialize camera system"""
        if self.camera.start_preview():
            self.camera_active = True
            self.start_enhanced_preview()
            self.update_status("SUCCESS Kamera advanced siap - Preview aktif")
        else:
            self.update_status("ERROR Kamera tidak dapat dihidupkan")
    
    def start_enhanced_preview(self):
        """Start camera preview"""
        if self.camera_active and not self.preview_updating:
            self.preview_updating = True
            self.update_enhanced_preview()
    
    def update_enhanced_preview(self):
        """Update camera preview dengan face detection/recognition"""
        if self.camera_active and self.preview_updating:
            try:
                frame = self.camera.get_frame()
                if frame is not None and PIL_AVAILABLE:
                    # Pastikan frame adalah PIL Image
                    if not isinstance(frame, Image.Image):
                        try:
                            frame = Image.fromarray(frame)
                        except Exception as e:
                            logger.error(f"ERROR Frame conversion error: {e}")
                            # Continue dengan frame simulasi jika gagal
                            frame = self.camera.create_simulation_frame()
                    
                    # Resize frame untuk canvas
                    frame_resized = frame.resize((640, 480), Image.Resampling.LANCZOS)
                    
                    # Convert PIL Image to PhotoImage
                    try:
                        photo = ImageTk.PhotoImage(frame_resized)
                        # Update canvas
                        self.camera_canvas.delete("all")
                        self.camera_canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                        self.camera_canvas.photo_ref = photo  # Keep reference to prevent garbage collection
                        
                        # Add overlay text
                        overlay_text = f"FPS: {self.camera.preview_fps}"
                        if self.face_detection_enabled:
                            overlay_text += " | FACE DETECTION ON"
                        if self.face_recognition_enabled:
                            overlay_text += " | FACE RECOGNITION ON"
                        
                        self.camera_canvas.create_text(320, 460, text=overlay_text, 
                                                     fill="white", font=('Arial', 12, 'bold'),
                                                     anchor=tk.CENTER)
                    except Exception as e:
                        logger.error(f"ERROR PhotoImage conversion error: {e}")
                        # Fallback: tampilkan teks error di canvas
                        self.camera_canvas.delete("all")
                        self.camera_canvas.create_text(320, 240, 
                                                     text=f"Preview Error:\n{str(e)}", 
                                                     fill="red", font=('Arial', 12), 
                                                     justify='center')
            except Exception as e:
                logger.error(f"ERROR Enhanced preview error: {e}")
                traceback.print_exc()
                # Fallback untuk error
                self.camera_canvas.delete("all")
                self.camera_canvas.create_text(320, 240, 
                                             text="Preview Error\nRestarting...", 
                                             fill="yellow", font=('Arial', 14, 'bold'), 
                                             justify='center')
            
            # Continue preview dengan delay sesuai FPS
            delay = int(1000 / self.camera.preview_fps)
            self.root.after(delay, self.update_enhanced_preview)
        else:
            self.preview_updating = False
    
    def toggle_camera_preview(self):
        """Toggle camera preview dengan safety check"""
        if self.camera_active:
            self.stop_enhanced_preview()
        else:
            self.start_enhanced_camera()
    
    def start_enhanced_camera(self):
        """Start enhanced camera"""
        if self.camera.start_preview():
            self.camera_active = True
            self.cam_btn.config(text="STOP PREVIEW", bg='#e74c3c')
            self.capture_btn.config(state=tk.NORMAL)  # Enable capture button
            
            status_text = "Preview aktif"
            if self.face_detection_enabled:
                status_text += " | Face Detection: ON"
            if self.face_recognition_enabled:
                status_text += " | Face Recognition: ON"
            
            self.camera_status.config(text=status_text, fg='#27ae60')
            self.update_status("SUCCESS Advanced preview kamera aktif")
            self.voice.speak("Preview kamera aktif")
            
            # Start preview dengan delay untuk memastikan kamera siap
            self.root.after(500, self.start_enhanced_preview)
        else:
            self.update_status("ERROR Gagal menghidupkan preview kamera")
    
    def stop_enhanced_preview(self):
        """Stop camera preview"""
        self.preview_updating = False  # Stop the update loop first
        
        if self.camera.stop_preview():
            self.camera_active = False
            self.cam_btn.config(text="START PREVIEW", bg='#27ae60')
            self.capture_btn.config(state=tk.DISABLED)  # Disable capture button
            self.camera_status.config(text="Preview dihentikan", fg='#e74c3c')
            self.update_status("Preview kamera dihentikan")
            self.voice.speak("Preview dihentikan")
            
            # Clear canvas dengan cara yang aman
            self.camera_canvas.delete("all")
            self.camera_canvas.create_text(320, 240, 
                                         text="PREVIEW DIHENTIKAN\nKlik START PREVIEW untuk mengaktifkan", 
                                         fill="white", font=('Arial', 14, 'bold'), 
                                         justify='center')
        else:
            self.update_status("ERROR Gagal menghentikan preview kamera")
    
    def capture_photo(self):
        """Capture photo dengan achievement"""
        if not self.camera.is_active:
            messagebox.showwarning("Peringatan", "Kamera tidak aktif!", parent=self.root)
            return
        
        self.capture_btn.config(state=tk.DISABLED)
        self.update_status("CAPTURE Mengambil foto...")
        self.add_conversation("CAPTURE: Mengambil foto...")
        self.voice.speak("Mengambil foto, harap diam sejenak")
        
        def capture_thread():
            try:
                # Generate nama file dengan timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"foto_penduduk_{timestamp}.jpg"
                foto_path = self.camera.capture_image(filename)
                
                if foto_path:
                    self.root.after(0, lambda: self.on_capture_success(foto_path))
                else:
                    self.root.after(0, self.on_capture_failed)
            finally:
                self.root.after(0, lambda: self.capture_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=capture_thread, daemon=True).start()
    
    def on_capture_success(self, foto_path):
        """Handle successful photo capture dengan achievement"""
        self.update_status(f"SUCCESS Foto berhasil disimpan di: {foto_path}")
        self.voice.speak("Foto berhasil diambil, senyumnya bagus!")
        self.add_conversation(f"SUCCESS: Foto berhasil diambil dan disimpan di {foto_path}")
        
        # Unlock achievement
        self.gamification.unlock_achievement(self.user_id, 'photo_taken')
        self.gamification.add_activity_point(self.user_id, 'photo_capture', 10)
    
    def on_capture_failed(self):
        """Handle failed photo capture"""
        self.update_status("ERROR Gagal mengambil foto")
        self.add_conversation("ERROR: Gagal mengambil foto")
        self.voice.speak("Maaf, gagal mengambil foto. Silakan coba lagi.")
    
    def scan_document(self):
        """Scan document untuk ekstrak NIK dengan achievement"""
        if not self.camera.is_active:
            messagebox.showwarning("Peringatan", "Kamera tidak aktif!", parent=self.root)
            return
        
        self.update_status("SCAN Memindai dokumen...")
        self.add_conversation("SCAN: Memindai dokumen...")
        self.voice.speak("Memindai dokumen, harap posisikan dokumen dengan jelas")
        
        def scan_thread():
            try:
                # Capture photo first dengan nama khusus untuk scan
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"scan_dokumen_{timestamp}.jpg"
                foto_path = self.camera.capture_image(filename)
                
                if foto_path:
                    # Process OCR
                    extracted_number = self.ocr.extract_nik_from_image(foto_path)
                    if extracted_number:
                        self.root.after(0, lambda: self.on_scan_success(extracted_number))
                    else:
                        self.root.after(0, self.on_scan_failed)
                else:
                    self.root.after(0, self.on_scan_failed)
            except Exception as e:
                logger.error(f"ERROR OCR scan error: {e}")
                self.root.after(0, self.on_scan_failed)
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def on_scan_success(self, extracted_number):
        """Handle successful OCR scan dengan achievement"""
        self.nik_entry.delete(0, tk.END)
        self.nik_entry.insert(0, extracted_number)
        
        # Cek apakah ini NIK
        data_warga = self.db.cari_warga(extracted_number)
        if data_warga:
            message = f"SUCCESS NIK ditemukan: {data_warga['nama']}"
            self.voice.speak(f"Data ditemukan untuk {data_warga['nama']}")
            self.add_conversation(f"SUCCESS: NIK {extracted_number} - {data_warga['nama']}")
            # Unlock achievement
            self.gamification.unlock_achievement(self.user_id, 'document_scan')
            self.gamification.add_activity_point(self.user_id, 'document_scanning', 15)
        else:
            message = f"WARNING NIK {extracted_number} tidak terdaftar"
            self.voice.speak("NIK tidak terdaftar di database, data baru akan dibuat")
            self.add_conversation(f"WARNING: NIK {extracted_number} tidak terdaftar")
        
        self.update_status(message)
    
    def on_scan_failed(self):
        """Handle failed OCR scan"""
        self.update_status("ERROR Gagal memindai dokumen")
        self.add_conversation("ERROR: Gagal membaca dokumen")
        self.voice.speak("Maaf, gagal membaca dokumen. Pastikan pencahayaan cukup dan dokumen terbaca jelas.")
    
    def reset_input(self):
        """Reset input field"""
        self.nik_entry.delete(0, tk.END)
        self.update_status("Input berhasil dibersihkan")
        self.voice.speak("Input sudah dibersihkan")
        self.add_conversation("RESET: Input dibersihkan")
    
    def handle_service(self, service_type):
        """Handle layanan dengan achievement"""
        if service_type == "CEK_DATA":
            self.cek_data_warga()
        elif service_type == "SHOW_ALL_DATA":
            self.tampilkan_semua_data()
        else:
            self.buat_surat(service_type)
    
    def cek_data_warga(self):
        """Cek data warga berdasarkan NIK"""
        nik = self.nik_entry.get().strip()
        if not nik:
            messagebox.showwarning("Peringatan", "Masukkan NIK terlebih dahulu!", parent=self.root)
            return
        
        if len(nik) != 16 or not nik.isdigit():
            messagebox.showwarning("Peringatan", "NIK harus 16 digit angka!", parent=self.root)
            return
        
        self.update_status(f"SEARCH Mencari data untuk NIK: {nik}...")
        self.voice.speak("Mencari data warga")
        
        def search_thread():
            data_warga = self.db.cari_warga(nik)
            if data_warga:
                self.root.after(0, lambda: self.show_warga_data(data_warga))
            else:
                self.root.after(0, lambda: self.show_warga_not_found(nik))
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def show_warga_data(self, data_warga):
        """Tampilkan data warga yang ditemukan"""
        messagebox.showinfo("Data Warga Ditemukan", 
                          f"NIK: {data_warga['nik']}\n"
                          f"Nama: {data_warga['nama']}\n"
                          f"Alamat: {data_warga['alamat']}\n"
                          f"Tanggal Lahir: {data_warga['tanggal_lahir']}\n"
                          f"Pekerjaan: {data_warga['pekerjaan']}",
                          parent=self.root)
        
        self.voice.speak(f"Data ditemukan untuk {data_warga['nama']}")
        self.add_conversation(f"SEARCH: Data ditemukan - {data_warga['nama']}")
        # Add activity point
        self.gamification.add_activity_point(self.user_id, 'data_check', 5)
        self.update_status(f"SUCCESS Data ditemukan untuk {data_warga['nama']}")
    
    def show_warga_not_found(self, nik):
        """Tampilkan pesan NIK tidak ditemukan"""
        response = messagebox.askyesno(
            "Data Tidak Ditemukan", 
            f"NIK {nik} tidak terdaftar. Apakah Anda ingin menambahkan data baru?",
            parent=self.root
        )
        
        if response:
            self.add_warga_dialog()
        else:
            self.voice.speak("Data tidak ditemukan")
            self.add_conversation("ERROR: Data tidak ditemukan")
            self.update_status("ERROR Data tidak ditemukan")
    
    def tampilkan_semua_data(self):
        """Tampilkan semua data warga"""
        self.update_status("LOADING Memuat semua data warga...")
        self.voice.speak("Menampilkan semua data warga")
        
        def load_data_thread():
            data_warga = self.db.get_all_warga()
            self.root.after(0, lambda: self.display_all_data(data_warga))
        
        threading.Thread(target=load_data_thread, daemon=True).start()
    
    def display_all_data(self, data_warga):
        """Tampilkan semua data warga di window baru"""
        if not data_warga:
            messagebox.showinfo("Data Kosong", "Tidak ada data warga", parent=self.root)
            self.update_status("INFO Tidak ada data warga")
            return
        # Buat window baru
        data_window = tk.Toplevel(self.root)
        data_window.title("Data Seluruh Warga")
        data_window.geometry("900x500")
        data_window.configure(bg='#ecf0f1')
        # Search frame
        search_frame = tk.Frame(data_window, bg='#ecf0f1')
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(search_frame, text="Cari:", bg='#ecf0f1').pack(side=tk.LEFT)
        search_entry = tk.Entry(search_frame, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        # Treeview untuk menampilkan data
        tree_frame = tk.Frame(data_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tree = ttk.Treeview(tree_frame, columns=('NIK', 'Nama', 'Alamat', 'TTL', 'Pekerjaan'), show='headings')
        # Define headings
        tree.heading('NIK', text='NIK', command=lambda: self.treeview_sort_column(tree, 'NIK', False))
        tree.heading('Nama', text='Nama', command=lambda: self.treeview_sort_column(tree, 'Nama', False))
        tree.heading('Alamat', text='Alamat', command=lambda: self.treeview_sort_column(tree, 'Alamat', False))
        tree.heading('TTL', text='TTL', command=lambda: self.treeview_sort_column(tree, 'TTL', False))
        tree.heading('Pekerjaan', text='Pekerjaan', command=lambda: self.treeview_sort_column(tree, 'Pekerjaan', False))
        # Set column widths
        tree.column('NIK', width=120, anchor='w')
        tree.column('Nama', width=150, anchor='w')
        tree.column('Alamat', width=250, anchor='w')
        tree.column('TTL', width=100, anchor='w')
        tree.column('Pekerjaan', width=100, anchor='w')
        # Add data
        for warga in data_warga:
            tree.insert('', 'end', values=(
                warga['nik'],
                warga['nama'],
                warga['alamat'],
                warga['tanggal_lahir'],
                warga['pekerjaan']
            ))
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        # Label jumlah data
        count_label = tk.Label(data_window, text=f"Total {len(data_warga)} warga terdaftar", 
                              font=('Arial', 10), bg='#ecf0f1', pady=5)
        count_label.pack(side=tk.BOTTOM, fill=tk.X)
        self.add_conversation(f"ALL DATA: Menampilkan {len(data_warga)} data warga")
        # Add activity point
        self.gamification.add_activity_point(self.user_id, 'show_all_data', 8)
        self.update_status(f"SUCCESS Menampilkan {len(data_warga)} data warga")
        # Setup search functionality
        def search_data(event=None):
            query = search_entry.get().lower()
            for item in tree.get_children():
                tree.delete(item)
            filtered_data = [
                warga for warga in data_warga
                if query in warga['nama'].lower() or 
                   query in warga['nik'].lower() or
                   query in warga['alamat'].lower()
            ]
            for warga in filtered_data:
                tree.insert('', 'end', values=(
                    warga['nik'],
                    warga['nama'],
                    warga['alamat'],
                    warga['tanggal_lahir'],
                    warga['pekerjaan']
                ))
            count_label.config(text=f"Total {len(filtered_data)} warga ditemukan dari {len(data_warga)}")
        search_entry.bind('<KeyRelease>', search_data)
        # Tombol export
        export_btn = tk.Button(data_window, text="EXPORT TO CSV", 
                             command=lambda: self.export_data_to_csv(data_warga),
                             bg='#3498db', fg='white')
        export_btn.pack(pady=5)
    
    def treeview_sort_column(self, tree, col, reverse):
        """Sort treeview column"""
        l = [(tree.set(k, col), k) for k in tree.get_children('')]
        l.sort(reverse=reverse)
        
        # Rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            tree.move(k, '', index)
        
        # Reverse sort next time
        tree.heading(col, command=lambda: self.treeview_sort_column(tree, col, not reverse))
    
    def export_data_to_csv(self, data_warga):
        """Export data warga ke CSV"""
        try:
            import csv
            from tkinter.filedialog import asksaveasfilename
            
            filename = asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Simpan Data Warga",
                parent=self.root
            )
            
            if not filename:
                return
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['NIK', 'Nama', 'Alamat', 'Tanggal Lahir', 'Pekerjaan'])
                for warga in data_warga:
                    writer.writerow([
                        warga['nik'],
                        warga['nama'],
                        warga['alamat'],
                        warga['tanggal_lahir'],
                        warga['pekerjaan']
                    ])
            
            messagebox.showinfo("Berhasil", f"Data berhasil diekspor ke {filename}", parent=self.root)
            self.update_status(f"SUCCESS Data diekspor ke {filename}")
            self.voice.speak("Data berhasil diekspor")
        
        except Exception as e:
            logger.error(f"ERROR Export CSV error: {e}")
            messagebox.showerror("Error", f"Gagal mengekspor  {e}", parent=self.root)
    
    def buat_surat(self, jenis_surat):
        """Buat surat berdasarkan jenis dengan achievement"""
        nik = self.nik_entry.get().strip()
        if not nik or len(nik) != 16 or not nik.isdigit():
            messagebox.showwarning("Peringatan", "Masukkan NIK 16 digit terlebih dahulu!", parent=self.root)
            return
        
        self.update_status(f"LOADING Mencari data untuk NIK: {nik}...")
        self.voice.speak("Mencari data warga untuk pembuatan surat")
        
        def process_surat_thread():
            data_warga = self.db.cari_warga(nik)
            if data_warga:
                self.root.after(0, lambda: self.generate_surat(jenis_surat, data_warga))
            else:
                self.root.after(0, lambda: self.handle_warga_not_found(nik, jenis_surat))
        
        threading.Thread(target=process_surat_thread, daemon=True).start()
    
    def generate_surat(self, jenis_surat, data_warga):
        """Generate dan tampilkan surat"""
        # Generate surat
        nomor_surat = f"{jenis_surat}/{datetime.datetime.now().strftime('%Y%m%d')}/{random.randint(100, 999)}"
        current_date = datetime.datetime.now().strftime('%d-%m-%Y')
        
        if jenis_surat == "SKTM":
            content = f"""
                                SURAT KETERANGAN TIDAK MAMPU (SKTM)
                                        Nomor: {nomor_surat}

Yang bertanda tangan di bawah ini Kepala Desa {self.get_desa_name()}, menerangkan bahwa:

        Nama    : {data_warga['nama']}
        NIK     : {data_warga['nik']}
        Alamat  : {data_warga['alamat']}

Berdasarkan data yang ada, yang bersangkutan benar-benar tidak mampu secara ekonomi
dan memerlukan surat keterangan ini untuk keperluan {self.get_purpose(jenis_surat)}.

Demikian surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya.

                                            {self.get_desa_name()}, {current_date}
                                            KEPALA DESA

                                            {self.get_kepala_desa_name()}
                                            NIP. {self.get_kepala_desa_nip()}
"""
        elif jenis_surat == "DOMISILI":
            content = f"""
                                SURAT KETERANGAN DOMISILI
                                        Nomor: {nomor_surat}

Yang bertanda tangan di bawah ini Kepala Desa {self.get_desa_name()}, menerangkan bahwa:

        Nama            : {data_warga['nama']}
        NIK             : {data_warga['nik']}
        Tempat/Tgl Lahir: {self.get_tempat_lahir(data_warga['tanggal_lahir'])}
        Pekerjaan       : {data_warga['pekerjaan']}
        Alamat          : {data_warga['alamat']}

Adalah benar-benar berdomisili di Desa {self.get_desa_name()} dan surat ini diberikan
untuk keperluan {self.get_purpose(jenis_surat)}.

Demikian surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya.

                                            {self.get_desa_name()}, {current_date}
                                            KEPALA DESA

                                            {self.get_kepala_desa_name()}
                                            NIP. {self.get_kepala_desa_nip()}
"""
        elif jenis_surat == "USAHA":
            content = f"""
                                SURAT KETERANGAN USAHA
                                        Nomor: {nomor_surat}
Yang bertanda tangan di bawah ini Kepala Desa {self.get_desa_name()}, menerangkan bahwa:
        Nama            : {data_warga['nama']}
        NIK             : {data_warga['nik']}
        Alamat          : {data_warga['alamat']}
Memiliki usaha yang berlokasi di {data_warga['alamat']} dengan 
jenis usaha {self.get_jenis_usaha()} yang telah beroperasi sejak 
{self.get_tahun_operasi()} dan merupakan usaha yang sah menurut 
pemerintah desa setempat.

Surat keterangan ini diberikan untuk keperluan {self.get_purpose(jenis_surat)}.
Demikian surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya.
                                            {self.get_desa_name()}, {current_date}
                                            KEPALA DESA
                                            {self.get_kepala_desa_name()}
                                            NIP. {self.get_kepala_desa_nip()}
"""
        elif jenis_surat == "PENGHASILAN":
            content = f"""
                                SURAT KETERANGAN PENGHASILAN
                                        Nomor: {nomor_surat}
Yang bertanda tangan di bawah ini Kepala Desa {self.get_desa_name()}, menerangkan bahwa:
        Nama            : {data_warga['nama']}
        NIK             : {data_warga['nik']}
        Pekerjaan       : {data_warga['pekerjaan']}
        Alamat          : {data_warga['alamat']}
Berdasarkan data yang ada, yang bersangkutan memiliki penghasilan rata-rata 
Rp. {self.get_rata_rata_penghasilan()},- (belum dipotong pajak) per bulan.
Surat keterangan ini diberikan untuk keperluan {self.get_purpose(jenis_surat)}.
Demikian surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya.
                                            {self.get_desa_name()}, {current_date}
                                            KEPALA DESA
                                            {self.get_kepala_desa_name()}
                                            NIP. {self.get_kepala_desa_nip()}
"""
        else:
            content = f"""
                                SURAT KETERANGAN
                                        Nomor: {nomor_surat}
Yang bertanda tangan di bawah ini Kepala Desa {self.get_desa_name()}, menerangkan bahwa:
        Nama            : {data_warga['nama']}
        NIK             : {data_warga['nik']}
        Alamat          : {data_warga['alamat']}
        Pekerjaan       : {data_warga['pekerjaan']}
Surat keterangan ini diberikan untuk keperluan {self.get_purpose(jenis_surat)}.
Demikian surat keterangan ini dibuat untuk dipergunakan sebagaimana mestinya.
                                            {self.get_desa_name()}, {current_date}
                                            KEPALA DESA
                                            {self.get_kepala_desa_name()}
                                            NIP. {self.get_kepala_desa_nip()}
"""

        # Simpan ke database
        self.db.simpan_surat(jenis_surat, data_warga['nik'], data_warga['nama'], content)
        
        # Tampilkan di window baru
        self.tampilkan_surat(jenis_surat, nomor_surat, content, data_warga)
        
        # Update status
        self.update_status(f"SUCCESS Surat {jenis_surat} untuk {data_warga['nama']} berhasil dibuat")
        
        # Unlock achievement
        self.gamification.unlock_achievement(self.user_id, 'service_completed')
        self.gamification.add_activity_point(self.user_id, 'service_completion', 20)
    
    def get_desa_name(self):
        """Dapatkan nama desa"""
        return "SUKAMAJU"
    
    def get_kepala_desa_name(self):
        """Dapatkan nama kepala desa"""
        return "ASEP SUTISNA, S.Sos"
    
    def get_kepala_desa_nip(self):
        """Dapatkan NIP kepala desa"""
        return "19750815 200012 1 001"
    
    def get_tempat_lahir(self, tanggal_lahir):
        """Dapatkan tempat lahir dari tanggal lahir"""
        # Di implementasi nyata, ini bisa diambil dari database
        return f"Sukamaju, {tanggal_lahir}"
    
    def get_purpose(self, jenis_surat):
        """Dapatkan tujuan pembuatan surat"""
        purposes = {
            "SKTM": "pengajuan bantuan sosial",
            "DOMISILI": "pengurusan administrasi kependudukan",
            "USAHA": "pengajuan izin usaha",
            "PENGHASILAN": "pengajuan kredit/pinjaman"
        }
        return purposes.get(jenis_surat, "keperluan administrasi")
    
    def get_jenis_usaha(self):
        """Dapatkan jenis usaha secara acak untuk contoh"""
        jenis_usaha = [
            "Perdagangan sembako",
            "Kuliner/warung makan",
            "Jasa servis elektronik",
            "Bengkel kendaraan",
            "Pertanian/peternakan"
        ]
        return random.choice(jenis_usaha)
    
    def get_tahun_operasi(self):
        """Dapatkan tahun operasi usaha"""
        current_year = datetime.datetime.now().year
        tahun_operasi = random.randint(current_year-10, current_year-1)
        return str(tahun_operasi)
    
    def get_rata_rata_penghasilan(self):
        """Dapatkan rata-rata penghasilan"""
        # Angka yang disesuaikan dengan UMR setempat
        penghasilan = random.choice([1500000, 2000000, 2500000, 3000000, 3500000])
        return f"{penghasilan:,}".replace(",", ".")
    
    def tampilkan_surat(self, jenis_surat, nomor_surat, content, data_warga):
        """Tampilkan surat di window baru"""
        # Buat window baru
        surat_window = tk.Toplevel(self.root)
        surat_window.title(f"Surat {jenis_surat}")
        surat_window.geometry("800x600")
        surat_window.configure(bg='#ecf0f1')
        
        # Header
        header_frame = tk.Frame(surat_window, bg='#2c3e50')
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(header_frame, text="PEMERINTAH DESA SUKAMAJU", font=('Arial', 14, 'bold'), 
                fg='white', bg='#2c3e50').pack()
        tk.Label(header_frame, text="KECAMATAN MAJU JAYA", font=('Arial', 12), 
                fg='white', bg='#2c3e50').pack()
        tk.Label(header_frame, text="KABUPATEN MAKMUR SEJAHTERA", font=('Arial', 12), 
                fg='white', bg='#2c3e50').pack(pady=(0, 10))
        
        # Konten surat
        content_frame = tk.Frame(surat_window, bg='white', padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Text widget untuk konten surat
        text_widget = scrolledtext.ScrolledText(content_frame, font=('Arial', 11), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)
        
        # Tombol
        btn_frame = tk.Frame(surat_window, bg='#ecf0f1')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        def salin_ke_clipboard():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.update_status("SUCCESS Teks surat disalin ke clipboard")
            self.voice.speak("Teks surat telah disalin ke clipboard")
        
        def simpan_ke_file():
            from tkinter.filedialog import asksaveasfilename
            filename = asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
                title="Simpan Surat",
                parent=surat_window
            )
            if filename:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(content)
                    messagebox.showinfo("Berhasil", f"Surat berhasil disimpan ke {filename}", parent=surat_window)
                    self.update_status(f"SUCCESS Surat disimpan ke {filename}")
                    self.voice.speak("Surat berhasil disimpan")
                except Exception as e:
                    messagebox.showerror("Error", f"Gagal menyimpan file: {e}", parent=surat_window)
        
        tk.Button(btn_frame, text="SALIN KE CLIPBOARD", command=salin_ke_clipboard,
                 bg='#3498db', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="SIMPAN KE FILE", command=simpan_ke_file,
                 bg='#27ae60', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="CETAK", 
                 command=lambda: self.cetak_surat(content, jenis_surat, data_warga),
                 bg='#e67e22', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="TUTUP", command=surat_window.destroy,
                 bg='#e74c3c', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=5)
    
    def cetak_surat(self, content, jenis_surat, data_warga):
        """Simulasi pencetakan surat"""
        try:
            # Di implementasi nyata, ini akan menggunakan library printing
            self.update_status(f"PRINT Mencetak surat {jenis_surat}...")
            self.voice.speak(f"Mencetak surat {jenis_surat} untuk {data_warga['nama']}")
            
            # Simulasi proses cetak
            def print_simulation():
                time.sleep(2)  # Simulasi waktu proses cetak
                self.root.after(0, lambda: messagebox.showinfo(
                    "Berhasil", 
                    f"Surat {jenis_surat} berhasil dicetak!", 
                    parent=self.root
                ))
                self.root.after(0, lambda: self.update_status(f"SUCCESS Surat {jenis_surat} berhasil dicetak"))
            
            threading.Thread(target=print_simulation, daemon=True).start()
            
        except Exception as e:
            logger.error(f"ERROR Cetak surat error: {e}")
            messagebox.showerror("Error", f"Gagal mencetak surat: {e}", parent=self.root)
            self.update_status(f"ERROR Gagal mencetak surat: {e}")
    
    def handle_warga_not_found(self, nik, jenis_surat):
        """Handle jika data warga tidak ditemukan"""
        response = messagebox.askyesno(
            "Data Tidak Ditemukan", 
            f"NIK {nik} tidak terdaftar. Apakah Anda ingin menambahkan data baru?",
            parent=self.root
        )
        if response:
            self.add_warga_dialog()
        else:
            self.voice.speak("Data tidak ditemukan, surat tidak dapat dibuat")
            self.add_conversation("ERROR: Data tidak ditemukan, pembuatan surat dibatalkan")
            self.update_status("ERROR Data tidak ditemukan, pembuatan surat dibatalkan")
    
    def update_user_stats_display(self):
        """Update display statistik user"""
        stats = self.gamification.get_user_stats(self.user_id)
        self.stats_label.config(text=(
            f"Poin Anda: {stats['total_points']}\n"
            f"Pencapaian: {stats['total_achievements']}\n"
            f"User ID: {self.user_id[:10]}..."
        ))
    
    def update_achievement_status(self):
        """Update status achievement di status bar"""
        stats = self.gamification.get_user_stats(self.user_id)
        self.achievement_status.config(text=f"Achievements: {stats['total_achievements']} | Points: {stats['total_points']}")
    
    def show_achievements(self):
        """Tampilkan achievements user"""
        achievements = self.gamification.get_user_achievements(self.user_id)
        
        # Buat window baru
        achievement_window = tk.Toplevel(self.root)
        achievement_window.title("Pencapaian Anda")
        achievement_window.geometry("600x400")
        achievement_window.configure(bg='#ecf0f1')
        
        # Header
        tk.Label(achievement_window, text=f"PENCAPAIAN USER: {self.user_id[:10]}...", 
                font=('Arial', 14, 'bold'), bg='#3498db', fg='white', pady=10).pack(fill=tk.X)
        
        # Stats
        stats = self.gamification.get_user_stats(self.user_id)
        tk.Label(achievement_window, text=f"Total Poin: {stats['total_points']} | Total Pencapaian: {stats['total_achievements']}",
                font=('Arial', 10, 'bold'), bg='#ecf0f1', pady=5).pack(pady=5)
        
        # Treeview untuk achievements
        tree_frame = tk.Frame(achievement_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(tree_frame, columns=('Nama', 'Poin', 'Tanggal'), show='headings')
        tree.heading('Nama', text='Nama Pencapaian')
        tree.heading('Poin', text='Poin')
        tree.heading('Tanggal', text='Tanggal Dicapai')
        
        tree.column('Nama', width=250, anchor='w')
        tree.column('Poin', width=80, anchor='center')
        tree.column('Tanggal', width=150, anchor='center')
        
        # Tambahkan data
        for achievement in achievements:
            tree.insert('', 'end', values=(
                achievement['name'],
                achievement['points'],
                achievement['unlocked_at'].split('T')[0] if achievement['unlocked_at'] else 'N/A'
            ))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Tutup button
        tk.Button(achievement_window, text="TUTUP", command=achievement_window.destroy,
                 bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'), width=10).pack(pady=10)
    
    def show_leaderboard(self):
        """Tampilkan leaderboard"""
        leaderboard = self.gamification.get_leaderboard(10)
        
        # Buat window baru
        lb_window = tk.Toplevel(self.root)
        lb_window.title("Leaderboard")
        lb_window.geometry("600x400")
        lb_window.configure(bg='#ecf0f1')
        
        # Header
        tk.Label(lb_window, text="LEADERBOARD - 10 USER TERATAS", 
                font=('Arial', 14, 'bold'), bg='#9b59b6', fg='white', pady=10).pack(fill=tk.X)
        
        # Treeview
        tree_frame = tk.Frame(lb_window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(tree_frame, columns=('Rank', 'User', 'Poin', 'Pencapaian'), show='headings')
        tree.heading('Rank', text='Rank')
        tree.heading('User', text='User ID')
        tree.heading('Poin', text='Total Poin')
        tree.heading('Pencapaian', text='Total Pencapaian')
        
        tree.column('Rank', width=50, anchor='center')
        tree.column('User', width=150, anchor='center')
        tree.column('Poin', width=100, anchor='center')
        tree.column('Pencapaian', width=100, anchor='center')
        
        # Tambahkan data dengan penomoran rank
        for i, user in enumerate(leaderboard, 1):
            tree.insert('', 'end', values=(
                i,
                user['user_id'][:10] + '...',
                user['total_points'],
                user['total_achievements']
            ))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Tutup button
        tk.Button(lb_window, text="TUTUP", command=lb_window.destroy,
                 bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'), width=10).pack(pady=10)
    
    def show_voice_help(self):
        """Tampilkan bantuan perintah suara"""
        help_text = """
        DAFTAR PERINTAH SUARA YANG DIDUKUNG:
        
        Perintah Sistem:
        - "Bangunkan/aktifkan wake word"
        - "Matikan wake word"
        - "Aktifkan continuous listening"
        - "Matikan continuous listening"
        - "Kecepatan suara cepat/lambat/normal"
        
        Perintah Kamera & Wajah:
        - "Aktifkan/Nonaktifkan deteksi wajah"
        - "Aktifkan/Nonaktifkan face recognition"
        - "Daftar wajah"
        - "Hidupkan/Matikan kamera"
        - "Ambil foto"
        - "Scan dokumen/NIK"
        
        Perintah Layanan:
        - "Buat SKTM"
        - "Buat surat domisili"
        - "Buat surat usaha"
        - "Buat surat penghasilan"
        - "Cek data [nama/NIK]"
        - "Tampilkan semua data"
        
        Perintah Umum:
        - "Halo Ojan" (wake word)
        - "Jam berapa sekarang?"
        - "Tanggal berapa hari ini?"
        - "Bagaimana cuaca hari ini?"
        - "Lambaikan tangan"
        - "Angguk kepala"
        - "Keluar dari aplikasi"
        
        CATATAN:
        - Untuk mode wake word, ucapkan "Ojan" terlebih dahulu
        - Sistem akan merespons setelah mendeteksi wake word
        - Pastikan dalam ruangan yang tidak terlalu bising
        """
        
        # Buat window baru
        help_window = tk.Toplevel(self.root)
        help_window.title("Bantuan Perintah Suara")
        help_window.geometry("700x500")
        help_window.configure(bg='#ecf0f1')
        
        # Header
        tk.Label(help_window, text="BANTUAN PERINTAH SUARA", 
                font=('Arial', 14, 'bold'), bg='#3498db', fg='white', pady=10).pack(fill=tk.X)
        
        # Scrolled text
        text_frame = tk.Frame(help_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = scrolledtext.ScrolledText(text_frame, font=('Arial', 11), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)
        
        # Tutup button
        tk.Button(help_window, text="TUTUP", command=help_window.destroy,
                 bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'), width=10).pack(pady=10)
    
    def advanced_cleanup(self):
        """Cleanup resources"""
        logger.info("CLEANUP Advanced cleanup initiated...")
        try:
            # Stop voice recognition
            self.voice.stop_listening()
            
            # Stop camera
            self.camera.cleanup()
            
            # Reset servos
            self.servo.cleanup()
            
            # Stop monitoring
            self.monitoring_active = False
            
            logger.info("SUCCESS Advanced cleanup completed")
        except Exception as e:
            logger.error(f"ERROR Advanced cleanup error: {e}")
    
    def __del__(self):
        """Destructor untuk cleanup"""
        self.advanced_cleanup()

# =============================================================================
# MAIN EXECUTION
# =============================================================================
if __name__ == "__main__":
    try:
        # Setup environment
        os.environ['DISPLAY'] = ':0'
        os.environ['XAUTHORITY'] = '/home/nalika/.Xauthority'
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info(f"INFO Received signal {sig}, initiating shutdown")
            if 'app' in globals() and app is not None:
                app.advanced_cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create application
        root = tk.Tk()
        app = AdvancedRobotDesaApp(root)
        
        # Start main loop
        logger.info("SUCCESS Application started successfully")
        root.mainloop()
        
    except Exception as e:
        logger.error(f"CRITICAL Application crashed: {e}")
        traceback.print_exc()
        sys.exit(1)
