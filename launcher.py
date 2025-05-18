import urllib.request
import subprocess
import os

import urllib.request
import zipfile
import subprocess
import os
import tempfile

ZIP_URL = "http://192.168.1.11:30007/static/client.zip"
ZIP_NAME = "client.zip"
TARGET_FOLDER = os.path.join(tempfile.gettempdir(), "messenger_client")

def download_and_extract():
    try:
        zip_path = os.path.join(tempfile.gettempdir(), ZIP_NAME)
        urllib.request.urlretrieve(ZIP_URL, zip_path)
        print("✅ client.zip 다운로드 완료")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(TARGET_FOLDER)
        print("✅ 압축 해제 완료")
        return True
    except Exception as e:
        print(f"❌ 다운로드 또는 압축 해제 실패: {e}")
        return False

def run_client():
    exe_path = os.path.join(TARGET_FOLDER, "client", "client.exe")
    try:
        print("🚀 클라이언트 실행 중...")
        subprocess.run(exe_path, shell=True)
    except Exception as e:
        print(f"❌ 실행 실패: {e}")

if __name__ == "__main__":
    if download_and_extract():
        run_client()