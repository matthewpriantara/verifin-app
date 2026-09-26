import os

target = r"C:\Users\fizzu\Documents\Github\gemastik19\verifin-app\backend\START_BACKEND.bat"
work_dir = r"C:\Users\fizzu\Documents\Github\gemastik19\verifin-app\backend"
icon = r"C:\Users\fizzu\Documents\Github\gemastik19\verifin-app\frontend\public\favicon.ico"

desktops = [
    r"C:\Users\fizzu\OneDrive\Desktop",
    os.path.join(os.environ["USERPROFILE"], "Desktop"),
]

for d in set(desktops):
    if os.path.exists(d):
        shortcut_path = os.path.join(d, "Start Verifin Backend.lnk")
        vbs_content = f'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target}"
oLink.WorkingDirectory = "{work_dir}"
oLink.IconLocation = "{icon}"
oLink.Description = "Start Verifin FastAPI Backend Server"
oLink.Save
'''
        vbs_path = os.path.join(work_dir, "_make_shortcut.vbs")
        with open(vbs_path, "w") as f:
            f.write(vbs_content)

        os.system(f'cscript //nologo "{vbs_path}"')

        if os.path.exists(vbs_path):
            os.remove(vbs_path)

        if os.path.exists(shortcut_path):
            print("SUCCESS: Created shortcut at ->", shortcut_path)
