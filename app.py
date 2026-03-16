from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import random, string, os, io, requests
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ministages2025secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ministages.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── CONFIG ──────────────────────────────────────────────────
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
MAIL_FROM = os.environ.get('MAIL_FROM', 'jamila.zenid@flargenteuil.com')
MAIL_FROM_NAME = os.environ.get('MAIL_FROM_NAME', 'Mini-Stages Lycée Fernand et Nadia Léger')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin2025')

ACADEMIES = ['ac-versailles.fr', 'ac-creteil.fr', 'ac-paris.fr']

LYCEE = {
    'nom': 'Lycée Polyvalent Fernand et Nadia Léger',
    'adresse': '7 Allée Fernand Léger, 95100 Argenteuil',
    'tel': '01 39 98 43 43',
}

FORMATIONS = [
    {'id': 'cap-coiffure',  'niveau': 'CAP',     'nom': 'Coiffure',                                        'emoji': '✂️',  'niveaux_eleves': ['4ème','3ème']},
    {'id': 'cap-psr',       'niveau': 'CAP',     'nom': 'Production et Service en Restauration',           'emoji': '🍽️', 'niveaux_eleves': ['4ème','3ème']},
    {'id': 'cap-aepe',      'niveau': 'CAP',     'nom': 'Accompagnement Éducatif Petite Enfance',          'emoji': '🧒',  'niveaux_eleves': ['4ème','3ème']},
    {'id': 'bp-coiffure',   'niveau': 'BAC PRO', 'nom': 'Coiffure',                                        'emoji': '💇',  'niveaux_eleves': ['4ème','3ème','2nde']},
    {'id': 'bp-ecp',        'niveau': 'BAC PRO', 'nom': 'Esthétique Cosmétique et Parfumerie',             'emoji': '💅',  'niveaux_eleves': ['4ème','3ème','2nde']},
    {'id': 'bp-aepa', 'niveau': 'BAC PRO', 'nom': 'Animation Enfance et Personnes Âgées',                  'emoji': '🎭', 'niveaux_eleves': ['4ème','3ème','2nde']},
    {'id': 'bp-assp',       'niveau': 'BAC PRO', 'nom': 'Accompagnement Soins et Services à la Personne',  'emoji': '🏥',  'niveaux_eleves': ['4ème','3ème','2nde']},
    {'id': 'bp-hps',        'niveau': 'BAC PRO', 'nom': 'Hygiène Propreté et Stérilisation',               'emoji': '🏨',  'niveaux_eleves': ['4ème','3ème','2nde']},
]

db = SQLAlchemy(app)

# ── MODÈLES ─────────────────────────────────────────────────
class Creneau(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    formation_id = db.Column(db.String(50), nullable=False)
    date         = db.Column(db.Date, nullable=False)
    heure_debut  = db.Column(db.String(10), nullable=False)
    heure_fin    = db.Column(db.String(10), nullable=False)
    salle        = db.Column(db.String(50), default='')
    professeur   = db.Column(db.String(100), default='')
    places_max   = db.Column(db.Integer, default=4)
    actif        = db.Column(db.Boolean, default=True)
    reservations = db.relationship('Reservation', backref='creneau', lazy=True)
    attentes     = db.relationship('ListeAttente', backref='creneau', lazy=True)

    @property
    def formation(self):
        return next((f for f in FORMATIONS if f['id'] == self.formation_id), None)

    @property
    def places_prises(self):
        return Reservation.query.filter_by(creneau_id=self.id, annulee=False).count()

    @property
    def places_restantes(self):
        return max(0, self.places_max - self.places_prises)

    @property
    def complet(self):
        return self.places_restantes <= 0

class Reservation(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    code             = db.Column(db.String(10), unique=True, nullable=False)
    creneau_id       = db.Column(db.Integer, db.ForeignKey('creneau.id'), nullable=False)
    eleve_nom        = db.Column(db.String(100), nullable=False)
    eleve_prenom     = db.Column(db.String(100), nullable=False)
    eleve_classe     = db.Column(db.String(50), default='')
    eleve_ddn        = db.Column(db.String(20), default='')
    resp_legal_nom   = db.Column(db.String(150), default='')
    resp_legal_tel   = db.Column(db.String(30), default='')
    etab_nom         = db.Column(db.String(200), nullable=False)
    etab_ville       = db.Column(db.String(100), default='')
    etab_email       = db.Column(db.String(200), nullable=False)
    etab_contact     = db.Column(db.String(100), default='')
    etab_tel         = db.Column(db.String(30), default='')
    date_reservation = db.Column(db.DateTime, default=datetime.now)
    annulee          = db.Column(db.Boolean, default=False)

class ListeAttente(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    creneau_id   = db.Column(db.Integer, db.ForeignKey('creneau.id'), nullable=False)
    etab_email   = db.Column(db.String(200), nullable=False)
    etab_nom     = db.Column(db.String(200), default='')
    token        = db.Column(db.String(30), unique=True, nullable=False)
    date_ajout   = db.Column(db.DateTime, default=datetime.now)
    notifie      = db.Column(db.Boolean, default=False)
    date_notif   = db.Column(db.DateTime, nullable=True)
    confirme     = db.Column(db.Boolean, default=False)

class MotDePasse(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(200), unique=True, nullable=False)
    code       = db.Column(db.String(10), nullable=False)
    date_envoi = db.Column(db.DateTime, default=datetime.now)

# ── HELPERS ─────────────────────────────────────────────────
def gen_code(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def email_ok(email):
    return any(email.lower().strip().endswith('@' + a) for a in ACADEMIES)

def envoyer_mail(dest, sujet, html, pieces=None):
    """Envoi via Brevo API"""
    if not BREVO_API_KEY:
        print(f"[MAIL SIMULÉ] À: {dest} | Sujet: {sujet}")
        return True
    payload = {
        "sender": {"name": MAIL_FROM_NAME, "email": MAIL_FROM},
        "to": [{"email": dest}],
        "subject": sujet,
        "htmlContent": html,
    }
    if pieces:
        payload["attachment"] = [{"name": n, "content": __import__('base64').b64encode(d).decode()} for n, d in pieces]
    try:
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
            json=payload, timeout=10
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"Erreur mail: {e}")
        return False

def get_formation(fid):
    return next((f for f in FORMATIONS if f['id'] == fid), None)

def notifier_suivant_attente(creneau_id):
    """Notifie le prochain en liste d'attente si une place se libère"""
    cr = Creneau.query.get(creneau_id)
    if not cr or cr.complet:
        return
    suivant = ListeAttente.query.filter_by(
        creneau_id=creneau_id, notifie=False, confirme=False
    ).order_by(ListeAttente.date_ajout).first()
    if not suivant:
        return
    f = cr.formation
    nom_formation = f"{f['niveau']} {f['nom']}" if f else "Formation"
    lien = url_for('confirmer_attente', token=suivant.token, _external=True)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:30px;background:#f0f7ff;border-radius:12px;">
      <h2 style="color:#1565c0;">🎉 Une place s'est libérée !</h2>
      <p>Bonjour,</p>
      <p>Une place vient de se libérer sur le créneau suivant :</p>
      <div style="background:#fff;border:2px solid #1565c0;border-radius:8px;padding:16px;margin:16px 0;">
        <b>Formation :</b> {nom_formation}<br>
        <b>Date :</b> {cr.date.strftime('%d/%m/%Y')}<br>
        <b>Horaires :</b> {cr.heure_debut} – {cr.heure_fin}<br>
        <b>Salle :</b> {cr.salle or '—'}
      </div>
      <p>Vous avez <strong>24 heures</strong> pour confirmer votre place en cliquant ci-dessous :</p>
      <a href="{lien}" style="display:inline-block;background:#1565c0;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;">Confirmer ma place →</a>
      <p style="color:#888;font-size:12px;margin-top:20px;">Sans confirmation dans les 24h, la place sera proposée au suivant.</p>
    </div>
    """
    if envoyer_mail(suivant.etab_email, f"Place disponible — {nom_formation} le {cr.date.strftime('%d/%m/%Y')}", html):
        suivant.notifie = True
        suivant.date_notif = datetime.now()
        db.session.commit()

def generer_convention_pdf(resa):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.8*cm, leftMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    bleu = colors.HexColor('#1565c0')
    styles = getSampleStyleSheet()
    story = []

    titre = ParagraphStyle('t', fontSize=15, fontName='Helvetica-Bold', textColor=bleu, alignment=TA_CENTER, spaceAfter=4)
    sous  = ParagraphStyle('s', fontSize=9,  fontName='Helvetica', textColor=colors.HexColor('#444'), alignment=TA_CENTER, spaceAfter=2)
    bold9 = ParagraphStyle('b', fontSize=9,  fontName='Helvetica-Bold', textColor=colors.black)
    norm8 = ParagraphStyle('n', fontSize=8,  fontName='Helvetica', textColor=colors.HexColor('#333'), leading=12, alignment=TA_JUSTIFY)
    label = ParagraphStyle('l', fontSize=7.5,fontName='Helvetica-Bold', textColor=colors.HexColor('#555'))

    story.append(Paragraph(LYCEE['nom'], titre))
    story.append(Paragraph(f"{LYCEE['adresse']} — Tél : {LYCEE['tel']}", sous))
    story.append(HRFlowable(width="100%", thickness=2, color=bleu, spaceAfter=10))
    story.append(Paragraph("CONVENTION DE MINI-STAGE — SÉQUENCE D'OBSERVATION", ParagraphStyle('cv', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=bleu, spaceAfter=12)))

    cr = resa.creneau
    f  = cr.formation
    nom_formation = f"{f['niveau']} {f['nom']}" if f else cr.formation_id

    brd = {'style': 'GRID', 'color': colors.HexColor('#c0d8f0')}

    # Infos stage
    t_stage = Table([
        [Paragraph('Formation', label), Paragraph(nom_formation, bold9)],
        [Paragraph('Date', label),      Paragraph(cr.date.strftime('%A %d %B %Y').capitalize(), bold9)],
        [Paragraph('Horaires', label),  Paragraph(f"{cr.heure_debut} – {cr.heure_fin}", bold9)],
        [Paragraph('Salle', label),     Paragraph(cr.salle or '—', bold9)],
        [Paragraph('Professeur', label),Paragraph(cr.professeur or '—', bold9)],
        [Paragraph('Code réservation', label), Paragraph(resa.code, bold9)],
    ], colWidths=[4*cm, 13*cm])
    t_stage.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#e3f0fb')),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#c0d8f0')),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.HexColor('#f0f7ff'),colors.white]),
        ('PADDING',(0,0),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(t_stage)
    story.append(Spacer(1, 0.4*cm))

    # 3 colonnes : élève | étab origine | étab accueil
    col_eleve = [
        Paragraph('<b>L\'ÉLÈVE</b>', ParagraphStyle('h', fontSize=8.5, fontName='Helvetica-Bold', textColor=bleu)),
        Spacer(1,4),
        Paragraph(f"Nom : {resa.eleve_nom}", norm8),
        Paragraph(f"Prénom : {resa.eleve_prenom}", norm8),
        Paragraph(f"Classe : {resa.eleve_classe or '—'}", norm8),
        Paragraph(f"Date de naissance : {resa.eleve_ddn or '—'}", norm8),
        Spacer(1,6),
        Paragraph('<b>RESPONSABLE LÉGAL</b>', ParagraphStyle('h2', fontSize=8, fontName='Helvetica-Bold', textColor=bleu)),
        Spacer(1,4),
        Paragraph(f"Nom : {resa.resp_legal_nom or '—'}", norm8),
        Paragraph(f"Tél : {resa.resp_legal_tel or '—'}", norm8),
    ]
    col_origine = [
        Paragraph('<b>ÉTABLISSEMENT D\'ORIGINE</b>', ParagraphStyle('h3', fontSize=8.5, fontName='Helvetica-Bold', textColor=bleu)),
        Spacer(1,4),
        Paragraph(f"Nom : {resa.etab_nom}", norm8),
        Paragraph(f"Ville : {resa.etab_ville or '—'}", norm8),
        Paragraph(f"Chef d'établissement : {resa.etab_contact or '—'}", norm8),
        Paragraph(f"Tél : {resa.etab_tel or '—'}", norm8),
        Paragraph(f"Mail : {resa.etab_email}", norm8),
    ]
    col_accueil = [
        Paragraph('<b>ÉTABLISSEMENT D\'ACCUEIL</b>', ParagraphStyle('h4', fontSize=8.5, fontName='Helvetica-Bold', textColor=bleu)),
        Spacer(1,4),
        Paragraph(f"Nom : {LYCEE['nom']}", norm8),
        Paragraph(f"Adresse : {LYCEE['adresse']}", norm8),
        Paragraph(f"Tél : {LYCEE['tel']}", norm8),
    ]

    t3col = Table([[col_eleve, col_origine, col_accueil]], colWidths=[5.7*cm, 5.7*cm, 5.7*cm])
    t3col.setStyle(TableStyle([
        ('BOX',(0,0),(0,0),0.5,colors.HexColor('#c0d8f0')),
        ('BOX',(1,0),(1,0),0.5,colors.HexColor('#c0d8f0')),
        ('BOX',(2,0),(2,0),0.5,colors.HexColor('#c0d8f0')),
        ('BACKGROUND',(0,0),(0,0),colors.HexColor('#f0f7ff')),
        ('BACKGROUND',(1,0),(1,0),colors.white),
        ('BACKGROUND',(2,0),(2,0),colors.HexColor('#f0f7ff')),
        ('PADDING',(0,0),(-1,-1),8),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
    ]))
    story.append(t3col)
    story.append(Spacer(1, 0.4*cm))

    # Dispositions générales
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#c0d8f0'), spaceAfter=8))
    story.append(Paragraph("DISPOSITIONS GÉNÉRALES", ParagraphStyle('dg', fontSize=9, fontName='Helvetica-Bold', textColor=bleu, spaceAfter=6)))
    dispos = [
        "La présente convention a pour objet de définir les modalités d'un mini-stage entre l'élève et son représentant légal, l'établissement d'origine et l'établissement d'accueil.",
        "Le trajet aller-retour de l'élève, entre son établissement d'origine ou son domicile et le lycée d'accueil, se fait sous la responsabilité et à la charge de sa famille.",
        "Durant le mini-stage, l'élève est associé aux activités proposées par l'établissement d'accueil. Il est soumis au règlement intérieur du lycée d'accueil.",
        "L'élève devra se présenter à l'accueil 10 minutes avant le début de la séquence muni de cette convention dûment complétée et signée.",
    ]
    for d in dispos:
        story.append(Paragraph(f"• {d}", norm8))
    story.append(Spacer(1, 0.5*cm))

    # Signatures
    story.append(Paragraph("SIGNATURES", ParagraphStyle('sig', fontSize=9, fontName='Helvetica-Bold', textColor=bleu, spaceAfter=8)))
    sig = Table([
        ['Responsable légal de l\'élève\n(signature)', 'Chef d\'établissement d\'origine\n(cachet + signature)', f'Établissement d\'accueil\n(cachet + signature)'],
        ['\n\n\n\n', '\n\n\n\n', '\n\n\n\n'],
        ['Date : ___________', 'Date : ___________', 'Date : ___________'],
    ], colWidths=[5.7*cm, 5.7*cm, 5.7*cm])
    sig.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('BOX',(0,0),(0,-1),0.5,colors.HexColor('#c0d8f0')),
        ('BOX',(1,0),(1,-1),0.5,colors.HexColor('#c0d8f0')),
        ('BOX',(2,0),(2,-1),0.5,colors.HexColor('#c0d8f0')),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e3f0fb')),
        ('PADDING',(0,0),(-1,-1),8),
    ]))
    story.append(sig)
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ── ROUTES ──────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', formations=FORMATIONS)

@app.route('/demander-mdp', methods=['GET','POST'])
def demander_mdp():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        if not email_ok(email):
            return render_template('demander_mdp.html', erreur="Adresse non autorisée. Utilisez une adresse académique (@ac-versailles.fr, @ac-creteil.fr ou @ac-paris.fr).")
        code = gen_code(6)
        existing = MotDePasse.query.filter_by(email=email).first()
        if existing:
            existing.code = code
            existing.date_envoi = datetime.now()
        else:
            db.session.add(MotDePasse(email=email, code=code))
        db.session.commit()
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;background:#f0f7ff;border-radius:12px;">
          <h2 style="color:#1565c0;">🎓 Mini-Stages — {LYCEE['nom']}</h2>
          <p>Voici votre mot de passe pour accéder aux réservations :</p>
          <div style="background:#fff;border:2px solid #1565c0;border-radius:8px;padding:20px;text-align:center;margin:20px 0;">
            <span style="font-size:30px;font-weight:bold;letter-spacing:8px;color:#1565c0;">{code}</span>
          </div>
          <p>Rendez-vous sur le site et saisissez ce code pour effectuer votre réservation.</p>
          <p style="color:#888;font-size:12px;">{LYCEE['nom']} — {LYCEE['adresse']}</p>
        </div>
        """
        envoyer_mail(email, f"Votre mot de passe — Mini-Stages {LYCEE['nom']}", html)
        return render_template('demander_mdp.html', succes=True, email=email)
    return render_template('demander_mdp.html')

@app.route('/reservation', methods=['GET','POST'])
def reservation():
    pwd = request.args.get('pwd') or request.form.get('pwd') or session.get('pwd_valide')
    mdp = MotDePasse.query.filter_by(code=pwd).first() if pwd else None
    if not mdp:
        flash("Mot de passe invalide.", "error")
        return redirect(url_for('index'))
    session['pwd_valide'] = pwd
    session['etab_email'] = mdp.email

    creneaux = Creneau.query.filter_by(actif=True).filter(Creneau.date >= date.today()).order_by(Creneau.date, Creneau.heure_debut).all()
    par_formation = {}
    for cr in creneaux:
        if cr.formation_id not in par_formation:
            par_formation[cr.formation_id] = []
        par_formation[cr.formation_id].append(cr)

    if request.method == 'POST':
        creneau_id = request.form.get('creneau_id')
        cr = Creneau.query.get(creneau_id)
        if not cr or not cr.actif:
            flash("Créneau introuvable.", "error")
            return redirect(url_for('reservation'))
        if cr.complet:
            flash("Ce créneau est complet.", "error")
            return redirect(url_for('reservation'))
        code = gen_code(8)
        resa = Reservation(
            code=code, creneau_id=cr.id,
            eleve_nom=request.form.get('eleve_nom','').strip().upper(),
            eleve_prenom=request.form.get('eleve_prenom','').strip(),
            eleve_classe=request.form.get('eleve_classe','').strip(),
            eleve_ddn=request.form.get('eleve_ddn','').strip(),
            resp_legal_nom=request.form.get('resp_legal_nom','').strip(),
            resp_legal_tel=request.form.get('resp_legal_tel','').strip(),
            etab_nom=request.form.get('etab_nom','').strip(),
            etab_ville=request.form.get('etab_ville','').strip(),
            etab_email=session['etab_email'],
            etab_contact=request.form.get('etab_contact','').strip(),
            etab_tel=request.form.get('etab_tel','').strip(),
        )
        db.session.add(resa)
        db.session.commit()
        pdf = generer_convention_pdf(resa)
        f = cr.formation
        nom_f = f"{f['niveau']} {f['nom']}" if f else cr.formation_id
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px;background:#f0f7ff;border-radius:12px;">
          <h2 style="color:#1565c0;">✅ Réservation confirmée</h2>
          <p>Bonjour,<br>La réservation suivante a bien été enregistrée :</p>
          <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <tr><td style="padding:7px;background:#e3f0fb;font-weight:bold;width:40%;">Formation</td><td style="padding:7px;">{nom_f}</td></tr>
            <tr><td style="padding:7px;background:#e3f0fb;font-weight:bold;">Date</td><td style="padding:7px;">{cr.date.strftime('%d/%m/%Y')}</td></tr>
            <tr><td style="padding:7px;background:#e3f0fb;font-weight:bold;">Horaires</td><td style="padding:7px;">{cr.heure_debut} – {cr.heure_fin}</td></tr>
            <tr><td style="padding:7px;background:#e3f0fb;font-weight:bold;">Élève</td><td style="padding:7px;">{resa.eleve_prenom} {resa.eleve_nom}</td></tr>
            <tr><td style="padding:7px;background:#e3f0fb;font-weight:bold;">Code réservation</td><td style="padding:7px;font-weight:bold;color:#1565c0;">{code}</td></tr>
          </table>
          <div style="background:#fff8ee;border:1px solid #fde8b0;border-radius:8px;padding:14px;margin:14px 0;">
            <b>⚠️ Important :</b> La convention ci-jointe doit être signée par :<br>
            • Le(s) responsable(s) légal(aux) de l'élève<br>
            • Le chef de votre établissement<br><br>
            <b>L'élève doit impérativement se présenter avec la convention signée.</b>
          </div>
          <p style="color:#555;font-size:12px;">{LYCEE['nom']} — {LYCEE['adresse']}</p>
        </div>
        """
        envoyer_mail(resa.etab_email, f"Confirmation mini-stage — {nom_f} le {cr.date.strftime('%d/%m/%Y')}", html, [(f"convention_{code}.pdf", pdf)])
        return redirect(url_for('confirmation', code=code))

    return render_template('reservation.html', formations=FORMATIONS, par_formation=par_formation, etab_email=session.get('etab_email'))

@app.route('/confirmation/<code>')
def confirmation(code):
    resa = Reservation.query.filter_by(code=code).first_or_404()
    return render_template('confirmation.html', resa=resa)

@app.route('/convention/<code>')
def telecharger_convention(code):
    resa = Reservation.query.filter_by(code=code).first_or_404()
    pdf = generer_convention_pdf(resa)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=f"convention_{code}.pdf")

@app.route('/liste-attente', methods=['POST'])
def liste_attente():
    creneau_id = request.form.get('creneau_id')
    pwd = session.get('pwd_valide')
    mdp = MotDePasse.query.filter_by(code=pwd).first() if pwd else None
    if not mdp:
        flash("Session expirée, reconnectez-vous.", "error")
        return redirect(url_for('index'))
    cr = Creneau.query.get_or_404(creneau_id)
    deja = ListeAttente.query.filter_by(creneau_id=creneau_id, etab_email=mdp.email, confirme=False).first()
    if deja:
        flash("Vous êtes déjà sur la liste d'attente pour ce créneau.", "info")
    else:
        token = gen_code(20)
        db.session.add(ListeAttente(creneau_id=cr.id, etab_email=mdp.email, etab_nom='', token=token))
        db.session.commit()
        f = cr.formation
        nom_f = f"{f['niveau']} {f['nom']}" if f else cr.formation_id
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;background:#f0f7ff;border-radius:12px;">
          <h2 style="color:#1565c0;">📋 Inscription liste d'attente</h2>
          <p>Vous êtes inscrit(e) sur la liste d'attente pour :</p>
          <div style="background:#fff;border:2px solid #1565c0;border-radius:8px;padding:14px;margin:14px 0;">
            <b>{nom_f}</b><br>
            {cr.date.strftime('%d/%m/%Y')} — {cr.heure_debut} à {cr.heure_fin}
          </div>
          <p>Vous serez notifié(e) par mail dès qu'une place se libère.</p>
        </div>
        """
        envoyer_mail(mdp.email, f"Liste d'attente — {nom_f}", html)
        flash("Vous avez été ajouté(e) à la liste d'attente. Vous serez notifié(e) par mail si une place se libère.", "success")
    return redirect(url_for('reservation'))

@app.route('/confirmer-attente/<token>')
def confirmer_attente(token):
    att = ListeAttente.query.filter_by(token=token, confirme=False).first_or_404()
    if att.date_notif and datetime.now() - att.date_notif > timedelta(hours=24):
        flash("Ce lien a expiré (24h). Vous avez été retiré de la liste.", "error")
        db.session.delete(att)
        db.session.commit()
        notifier_suivant_attente(att.creneau_id)
        return redirect(url_for('index'))
    session['pwd_valide'] = MotDePasse.query.filter_by(email=att.etab_email).first().code if MotDePasse.query.filter_by(email=att.etab_email).first() else None
    session['etab_email'] = att.etab_email
    att.confirme = True
    db.session.commit()
    flash("Place confirmée ! Complétez votre réservation.", "success")
    cr = Creneau.query.get(att.creneau_id)
    return redirect(url_for('reservation') + f"?creneau_preselect={att.creneau_id}")

@app.route('/gerer', methods=['GET','POST'])
def gerer():
    resa = None
    erreur = None
    if request.method == 'POST':
        code = request.form.get('code','').strip().upper()
        resa = Reservation.query.filter_by(code=code, annulee=False).first()
        if not resa:
            erreur = "Code introuvable ou réservation déjà annulée."
    return render_template('gerer.html', resa=resa, erreur=erreur,
                           creneaux_dispos=_creneaux_dispos_pour(resa) if resa else [])

def _creneaux_dispos_pour(resa):
    if not resa:
        return []
    return Creneau.query.filter_by(actif=True, formation_id=resa.creneau.formation_id).filter(
        Creneau.date >= date.today(), Creneau.id != resa.creneau_id
    ).all()

@app.route('/modifier/<code>', methods=['POST'])
def modifier(code):
    resa = Reservation.query.filter_by(code=code, annulee=False).first_or_404()
    nouveau_creneau_id = request.form.get('nouveau_creneau_id')
    nouveau = Creneau.query.get(nouveau_creneau_id)
    if not nouveau or nouveau.complet:
        flash("Ce créneau n'est plus disponible.", "error")
        return redirect(url_for('gerer'))
    ancien = resa.creneau
    resa.creneau_id = nouveau.id
    db.session.commit()
    notifier_suivant_attente(ancien.id)
    f = nouveau.formation
    nom_f = f"{f['niveau']} {f['nom']}" if f else ''
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;background:#f0f7ff;border-radius:12px;">
      <h2 style="color:#1565c0;">✏️ Réservation modifiée</h2>
      <p>Votre réservation <b>{code}</b> a été déplacée sur :</p>
      <div style="background:#fff;border:2px solid #1565c0;border-radius:8px;padding:14px;margin:14px 0;">
        <b>{nom_f}</b><br>
        {nouveau.date.strftime('%d/%m/%Y')} — {nouveau.heure_debut} à {nouveau.heure_fin}<br>
        Salle : {nouveau.salle or '—'}
      </div>
      <p>Une nouvelle convention vous est envoyée en pièce jointe.</p>
    </div>
    """
    pdf = generer_convention_pdf(resa)
    envoyer_mail(resa.etab_email, f"Modification réservation {code}", html, [(f"convention_{code}.pdf", pdf)])
    flash("Réservation modifiée avec succès. Une nouvelle convention vous a été envoyée.", "success")
    return redirect(url_for('gerer'))

@app.route('/annuler/<code>', methods=['POST'])
def annuler(code):
    resa = Reservation.query.filter_by(code=code, annulee=False).first_or_404()
    creneau_id = resa.creneau_id
    resa.annulee = True
    db.session.commit()
    notifier_suivant_attente(creneau_id)
    cr = resa.creneau
    f = cr.formation
    nom_f = f"{f['niveau']} {f['nom']}" if f else ''
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;">
      <h2 style="color:#d94f4f;">❌ Annulation confirmée</h2>
      <p>La réservation <b>{code}</b> ({resa.eleve_prenom} {resa.eleve_nom} — {nom_f} le {cr.date.strftime('%d/%m/%Y')}) a bien été annulée.</p>
    </div>
    """
    envoyer_mail(resa.etab_email, f"Annulation réservation {code}", html)
    flash("Réservation annulée.", "success")
    return redirect(url_for('gerer'))

# ── ADMIN ────────────────────────────────────────────────────

@app.route('/admin', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash("Mot de passe incorrect.", "error")
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    creneaux = Creneau.query.order_by(Creneau.date, Creneau.heure_debut).all()
    reservations = Reservation.query.filter_by(annulee=False).order_by(Reservation.date_reservation.desc()).all()
    attentes = ListeAttente.query.filter_by(confirme=False).order_by(ListeAttente.date_ajout).all()
    return render_template('admin_dashboard.html', creneaux=creneaux, reservations=reservations, attentes=attentes, formations=FORMATIONS, today=date.today())

@app.route('/admin/creneau/ajouter', methods=['POST'])
@admin_required
def admin_ajouter():
    try:
        db.session.add(Creneau(
            formation_id=request.form['formation_id'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            heure_debut=request.form['heure_debut'],
            heure_fin=request.form['heure_fin'],
            salle=request.form.get('salle',''),
            professeur=request.form.get('professeur',''),
            places_max=int(request.form.get('places_max', 4)),
        ))
        db.session.commit()
        flash("Créneau ajouté.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/creneau/supprimer/<int:id>', methods=['POST'])
@admin_required
def admin_supprimer(id):
    cr = Creneau.query.get_or_404(id)
    cr.actif = False
    db.session.commit()
    flash("Créneau désactivé.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/convention/<code>')
@admin_required
def admin_convention(code):
    resa = Reservation.query.filter_by(code=code).first_or_404()
    pdf = generer_convention_pdf(resa)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=f"convention_{code}.pdf")

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

# ── INIT DB ─────────────────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        if Creneau.query.count() == 0:
            for cr in [
                Creneau(formation_id='bp-ecp',     date=date(2025,3,23), heure_debut='08:00', heure_fin='10:00', salle='A002', professeur='Mme KRAISIN', places_max=2),
                Creneau(formation_id='bp-ecp',     date=date(2025,3,23), heure_debut='10:00', heure_fin='12:00', salle='A002', professeur='Mme KRAISIN', places_max=2),
                Creneau(formation_id='bp-coiffure',date=date(2025,3,26), heure_debut='08:00', heure_fin='12:00', salle='C200', professeur='Mme MORGADO', places_max=4),
                Creneau(formation_id='bp-coiffure',date=date(2025,4,2),  heure_debut='08:00', heure_fin='12:00', salle='C200', professeur='Mme MORGADO', places_max=4),
            ]:
                db.session.add(cr)
            db.session.commit()

init_db()

if __name__ == '__main__':
    app.run(debug=True)
