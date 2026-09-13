from flask import Flask, render_template, request, redirect, url_for, send_file
import pandas as pd
import os
import socket
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from werkzeug.utils import secure_filename

app = Flask(__name__)
CSV_FILE = "certificates.csv"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure CSV exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w") as f:
        f.write("certificate_id,student_name,course,issue_date,institution,status,email\n")

# --- Auto Detect Laptop IP ---
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# --- QR Code Generate Function ---
def generate_qr(cert_id):
    os.makedirs("qrcodes", exist_ok=True)
    qr_path = os.path.join("qrcodes", f"{cert_id}.png")
    ip = get_ip()
    url = f"http://{ip}:5000/verify?certificate_id={cert_id}"
    img = qrcode.make(url)
    img.save(qr_path)
    return qr_path, url

# --- PDF Generate Function ---
def generate_pdf(cert):
    os.makedirs("certificates", exist_ok=True)
    file_path = os.path.join("certificates", f"{cert['certificate_id']}.pdf")

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # 🔧 Institution Logo
    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        c.drawImage(logo_path, width/2-40, height-120, width=80, height=80)

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height-180, "🎓 Certificate of Completion")

    c.setFont("Helvetica", 14)
    c.drawString(100, height-220, f"Certificate ID: {cert['certificate_id']}")
    c.drawString(100, height-250, f"Student Name: {cert['student_name']}")
    c.drawString(100, height-280, f"Course: {cert['course']}")
    c.drawString(100, height-310, f"Issue Date: {cert['issue_date']}")
    c.drawString(100, height-340, f"Institution: {cert['institution']}")
    c.drawString(100, height-370, f"Status: {cert['status']}")

    qr_path, url = generate_qr(cert['certificate_id'])
    qr_img = ImageReader(qr_path)
    c.drawImage(qr_img, width-200, 150, width=100, height=100)

    c.setFont("Helvetica", 10)
    c.drawString(width-200, 140, url)

    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(width/2, 100, "Scan QR to verify certificate online.")

    c.showPage()
    c.save()
    return file_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/verify', methods=['POST','GET'])
def verify():
    cert_id = request.values.get("certificate_id")
    df = pd.read_csv(CSV_FILE, dtype=str)
    cert = df.loc[df["certificate_id"] == cert_id].to_dict(orient="records")
    if cert:
        return render_template("result.html", certificate=cert[0])
    else:
        return render_template("result.html", certificate=None)

@app.route('/admin')
def admin():
    df = pd.read_csv(CSV_FILE, dtype=str)
    return render_template("admin.html", certificates=df.to_dict(orient="records"))

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return redirect(url_for("admin"))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for("admin"))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)

        df_main = pd.read_csv(CSV_FILE, dtype=str)
        df_new = pd.read_csv(filepath, dtype=str)
        df_all = pd.concat([df_main, df_new], ignore_index=True)
        df_all.to_csv(CSV_FILE, index=False)

        return redirect(url_for("admin"))
    else:
        return redirect(url_for("admin"))

@app.route('/add', methods=['POST'])
def add_certificate():
    df = pd.read_csv(CSV_FILE, dtype=str)
    new_row = {
        "certificate_id": request.form.get("certificate_id"),
        "student_name": request.form.get("student_name"),
        "course": request.form.get("course"),
        "issue_date": request.form.get("issue_date"),
        "institution": request.form.get("institution"),
        "status": request.form.get("status"),
        "email": request.form.get("email")
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)
    return redirect(url_for("admin"))

@app.route('/edit/<cert_id>', methods=['GET','POST'])
def edit_certificate(cert_id):
    df = pd.read_csv(CSV_FILE, dtype=str)
    cert = df.loc[df["certificate_id"] == cert_id].to_dict(orient="records")
    if request.method == 'POST':
        df.loc[df["certificate_id"] == cert_id, "student_name"] = request.form.get("student_name")
        df.loc[df["certificate_id"] == cert_id, "course"] = request.form.get("course")
        df.loc[df["certificate_id"] == cert_id, "issue_date"] = request.form.get("issue_date")
        df.loc[df["certificate_id"] == cert_id, "institution"] = request.form.get("institution")
        df.loc[df["certificate_id"] == cert_id, "status"] = request.form.get("status")
        df.loc[df["certificate_id"] == cert_id, "email"] = request.form.get("email")
        df.to_csv(CSV_FILE, index=False)
        return redirect(url_for("admin"))
    return render_template("edit.html", certificate=cert[0])

@app.route('/delete/<cert_id>')
def delete_certificate(cert_id):
    df = pd.read_csv(CSV_FILE, dtype=str)
    df = df[df["certificate_id"] != cert_id]
    df.to_csv(CSV_FILE, index=False)
    return redirect(url_for("admin"))

@app.route('/download/<cert_id>')
def download_certificate(cert_id):
    df = pd.read_csv(CSV_FILE, dtype=str)
    cert = df.loc[df["certificate_id"] == cert_id].to_dict(orient="records")
    if cert:
        file_path = generate_pdf(cert[0])
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return f"PDF not generated for {cert_id}"
    else:
        return f"Certificate ID {cert_id} not found in CSV!"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)





