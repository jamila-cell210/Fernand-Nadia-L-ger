from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import random, string, os, io, requests
from functools import wraps
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ministages2025secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ministages.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

MAIL_FROM = os.environ.get('MAIL_FROM', 'ministagesfernandleger@gmail.com')
MAIL_NOTIF = 'ministagesfernandleger@gmail.com'
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin2025')
ACADEMIES = ['ac-versailles.fr', 'ac-creteil.fr', 'ac-paris.fr']
SITE_URL = os.environ.get('SITE_URL', 'https://ministages-fernandnadialeger.onrender.com')

LYCEE = {
    'nom': 'Lycée Polyvalent Fernand et Nadia Léger',
    'adresse': '7 Allée Fernand Léger, 95100 Argenteuil',
    'tel': '01 39 98 43 43',
    'email': '0951811c@ac-versailles.fr',
}

FORMATIONS = [
    {'id': 'cap-coiffure', 'niveau': 'CAP', 'nom': 'Coiffure', 'emoji': '✂️', 'niveaux_eleves': ['4ème','3ème'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/cap-metiers-de-la-coiffure'},
    {'id': 'cap-psr', 'niveau': 'CAP', 'nom': 'Production et Service en Restauration', 'emoji': '🍽️', 'niveaux_eleves': ['4ème','3ème'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/cap-production-et-service-en-restaurations-rapide-collective-cafeteria'},
    {'id': 'cap-aepe', 'niveau': 'CAP', 'nom': 'Accompagnement Éducatif Petite Enfance', 'emoji': '🧒', 'niveaux_eleves': ['4ème','3ème'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/cap-accompagnant-educatif-petite-enfance'},
    {'id': 'bp-coiffure', 'niveau': 'BAC PRO', 'nom': 'Coiffure', 'emoji': '💇', 'niveaux_eleves': ['3ème','2nde'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/bac-pro-metiers-de-la-coiffure'},
    {'id': 'bp-ecp', 'niveau': 'BAC PRO', 'nom': 'Esthétique Cosmétique et Parfumerie', 'emoji': '💅', 'niveaux_eleves': ['3ème','2nde'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/bac-pro-esthetique-cosmetique-parfumerie'},
    {'id': 'bp-aepa', 'niveau': 'BAC PRO', 'nom': 'Animation Enfance et Personnes Âgées', 'emoji': '👶', 'niveaux_eleves': ['3ème','2nde'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/bac-pro-animation-enfance-et-personnes-agees'},
    {'id': 'bp-assp', 'niveau': 'BAC PRO', 'nom': 'Accompagnement Soins et Services à la Personne', 'emoji': '🏥', 'niveaux_eleves': ['3ème','2nde'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/bac-pro-accompagnement-soins-et-services-a-la-personne'},
    {'id': 'bp-hps', 'niveau': 'BAC PRO', 'nom': 'Hygiène Propreté et Stérilisation', 'emoji': '🧹', 'niveaux_eleves': ['3ème','2nde'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/bac-pro-hygiene-proprete-sterilisation'},
    {'id': 'bt-st2s', 'niveau': 'BAC TECHNO', 'nom': 'Sciences et Technologies de la Santé et du Social', 'emoji': '🔬', 'niveaux_eleves': ['3ème','2nde'], 'onisep': 'https://www.onisep.fr/ressources/univers-formation/formations/lycees/bac-techno-st2s-sciences-et-technologies-de-la-sante-et-du-social'},
]

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

def date_fr(d):
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month-1]} {d.year}"

db = SQLAlchemy(app)

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
    id                = db.Column(db.Integer, primary_key=True)
    code              = db.Column(db.String(10), unique=True, nullable=False)
    creneau_id        = db.Column(db.Integer, db.ForeignKey('creneau.id'), nullable=False)
    eleve_nom         = db.Column(db.String(100), nullable=False)
    eleve_prenom      = db.Column(db.String(100), nullable=False)
    eleve_classe      = db.Column(db.String(50), default='')
    eleve_ddn         = db.Column(db.String(20), default='')
    resp_legal_nom    = db.Column(db.String(150), default='')
    resp_legal_tel    = db.Column(db.String(30), default='')
    resp_legal_email  = db.Column(db.String(200), default='')
    etab_nom          = db.Column(db.String(200), nullable=False)
    etab_ville        = db.Column(db.String(100), default='')
    etab_email        = db.Column(db.String(200), nullable=False)
    etab_email_direct = db.Column(db.String(200), default='')
    etab_contact      = db.Column(db.String(100), default='')
    etab_tel          = db.Column(db.String(30), default='')
    contact_nom       = db.Column(db.String(100), default='')
    contact_prenom    = db.Column(db.String(100), default='')
    contact_tel       = db.Column(db.String(30), default='')
    contact_email     = db.Column(db.String(200), default='')
    remarques         = db.Column(db.Text, default='')
    date_reservation  = db.Column(db.DateTime, default=datetime.now)
    annulee           = db.Column(db.Boolean, default=False)

class MotDePasse(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(200), unique=True, nullable=False)
    code       = db.Column(db.String(10), nullable=False)
    date_envoi = db.Column(db.DateTime, default=datetime.now)

def gen_code(n=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

def email_ok(email):
    return any(email.lower().strip().endswith('@' + a) for a in ACADEMIES)

def envoyer_mail(dest, sujet, html, pieces=None):
    if isinstance(dest, str):
        dest = [dest]
    dest = [d for d in dest if d and d.strip()]
    if not dest:
        return False
    try:
        payload = {
            "sender": {"name": "Mini-Stages Lycée Fernand et Nadia Léger", "email": MAIL_FROM},
            "to": [{"email": d} for d in dest],
            "subject": sujet,
            "htmlContent": html,
        }
        if pieces:
            payload["attachment"] = [{"name": n, "content": __import__('base64').b64encode(d).decode()} for n, d in pieces]
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": os.environ.get('BREVO_API_KEY', ''), "Content-Type": "application/json"},
            json=payload, timeout=15
        )
        print(f"Mail: {r.status_code} {r.text}")
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"Erreur mail: {e}")
        return False

def destinataires_resa(resa):
    tous = [
        resa.etab_email,
        resa.etab_email_direct,
        resa.contact_email,
        resa.resp_legal_email,
    ]
    return list(dict.fromkeys(d for d in tous if d and d.strip()))

def generer_convention_pdf(resa):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.2*cm, leftMargin=1.2*cm,
                            topMargin=0.7*cm, bottomMargin=0.7*cm)
    bleu = colors.HexColor('#1565c0')
    noir = colors.black
    gris = colors.HexColor('#555555')
    story = []

    s_titre = ParagraphStyle('titre', fontSize=12, fontName='Helvetica-Bold', textColor=bleu, alignment=TA_CENTER, spaceAfter=1)
    s_sous  = ParagraphStyle('sous', fontSize=7.5, fontName='Helvetica', textColor=gris, alignment=TA_CENTER, spaceAfter=3)
    s_obj   = ParagraphStyle('obj', fontSize=8, fontName='Helvetica', textColor=noir, spaceAfter=3, leading=11)
    s_bold  = ParagraphStyle('bold', fontSize=8, fontName='Helvetica-Bold', textColor=noir, leading=11)
    s_norm  = ParagraphStyle('norm', fontSize=7.5, fontName='Helvetica', textColor=noir, leading=11)
    s_sig   = ParagraphStyle('sig', fontSize=7.5, fontName='Helvetica-Bold', textColor=noir, alignment=TA_CENTER)
    s_dispo = ParagraphStyle('dispo', fontSize=7.5, fontName='Helvetica', textColor=noir, leading=11, leftIndent=8)

    cr = resa.creneau
    f = cr.formation
    nom_formation = f"{f['niveau']} {f['nom']}" if f else cr.formation_id
    contact_display = f"{resa.contact_nom} {resa.contact_prenom}".strip() if resa.contact_nom else resa.etab_contact

    logo_path = os.path.join(os.path.dirname(__file__), 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=3*cm, height=1.8*cm)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 0.1*cm))
        except:
            pass

    story.append(Paragraph(LYCEE['nom'], s_titre))
    story.append(Paragraph(f"{LYCEE['adresse']} — Tél : {LYCEE['tel']} — {LYCEE['email']}", s_sous))
    story.append(HRFlowable(width="100%", thickness=1.5, color=bleu, spaceAfter=4))
    story.append(Paragraph("CONVENTION DE MINI-STAGE — Séquence d'observation", ParagraphStyle('cvt', fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=bleu, spaceAfter=3)))
    story.append(Paragraph("<b>Objectif :</b> Permettre la découverte des formations dispensées par le lycée pour parfaire l'orientation des élèves.", s_obj))
    story.append(Paragraph("Il a été convenu ce qui suit entre :", s_obj))

    def cell(content):
        return [Paragraph(c, s_norm) for c in content]

    col_eleve = cell([
        "<b>L'ÉLÈVE</b>",
        f"Nom : {resa.eleve_nom}",
        f"Prénom : {resa.eleve_prenom}",
        f"Classe : {resa.eleve_classe or '___'}",
        f"Date de naissance : {resa.eleve_ddn or '___'}",
        " ",
        "<b>Responsable légal :</b>",
        f"Nom : {resa.resp_legal_nom or '___'}",
        f"Tél : {resa.resp_legal_tel or '___'}",
    ])
    col_origine = cell([
        "<b>ÉTABLISSEMENT D'ORIGINE</b>",
        f"Nom : {resa.etab_nom}",
        f"Représenté par (CE) : {resa.etab_contact or '___'}",
        f"Tél : {resa.etab_tel or '___'}",
        " ",
        "<b>Demandeur du mini-stage :</b>",
        f"Nom : {contact_display or '___'}",
        f"Mail : {resa.contact_email or resa.etab_email}",
    ])
    col_accueil = cell([
        "<b>ÉTABLISSEMENT D'ACCUEIL</b>",
        f"Nom : {LYCEE['nom']}",
        f"Adresse : {LYCEE['adresse']}",
        f"Tél : {LYCEE['tel']}",
        f"Mail : {LYCEE['email']}",
    ])

    t3 = Table([[col_eleve, col_origine, col_accueil]], colWidths=[6*cm, 6*cm, 6*cm])
    t3.setStyle(TableStyle([
        ('BOX', (0,0), (0,0), 0.5, colors.HexColor('#aaaaaa')),
        ('BOX', (1,0), (1,0), 0.5, colors.HexColor('#aaaaaa')),
        ('BOX', (2,0), (2,0), 0.5, colors.HexColor('#aaaaaa')),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#f0f7ff')),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor('#f0f7ff')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Détails du mini-stage :", s_bold))
    story.append(Spacer(1, 0.1*cm))

    t_stage = Table([
        [Paragraph('Formation', s_bold), Paragraph(nom_formation, s_norm),
         Paragraph('Date', s_bold), Paragraph(date_fr(cr.date), s_norm)],
        [Paragraph('Horaires', s_bold), Paragraph(f"{cr.heure_debut} – {cr.heure_fin}", s_norm),
         Paragraph('Salle', s_bold), Paragraph(cr.salle or '—', s_norm)],
        [Paragraph('Référent', s_bold), Paragraph(cr.professeur or '—', s_norm),
         Paragraph('Code réservation', s_bold), Paragraph(resa.code, s_norm)],
    ], colWidths=[3*cm, 6*cm, 3*cm, 6*cm])
    t_stage.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e8f0fb')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#e8f0fb')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_stage)

    if resa.remarques:
        story.append(Spacer(1, 0.1*cm))
        story.append(Paragraph(f"<b>Remarques :</b> {resa.remarques}", s_norm))

    story.append(Spacer(1, 0.2*cm))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#cccccc'), spaceAfter=4))
    story.append(Paragraph("Dispositions générales", s_bold))
    story.append(Spacer(1, 0.1*cm))

    for d in [
        "La présente convention a pour objet de définir les modalités d'un mini-stage entre l'élève et son représentant légal, l'établissement d'origine et l'établissement d'accueil.",
        "Le trajet aller-retour de l'élève se fait sous la responsabilité et à la charge de sa famille.",
        "Durant le mini-stage, l'élève est soumis au règlement intérieur du lycée d'accueil. Sa participation ne doit pas porter préjudice au bon déroulement des cours. Le Proviseur se réserve le droit de faire respecter ce règlement.",
        "Le Chef d'établissement d'origine contracte une assurance couvrant la responsabilité civile de l'élève. Le Proviseur du lycée d'accueil contracte une assurance pour les dommages dont l'élève pourrait être victime.",
    ]:
        story.append(Paragraph(f"• {d}", s_dispo))

    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "<b>L'élève devra se présenter à l'accueil 10 minutes avant le début de la séquence muni de cette convention dûment complétée.</b>",
        ParagraphStyle('imp', fontSize=8, fontName='Helvetica-Bold', textColor=bleu, leading=11)
    ))
    story.append(Spacer(1, 0.3*cm))

    sig = Table([
        [
            Paragraph("Signature du responsable légal de l'élève", s_sig),
            Paragraph("Cachet et signature de l'établissement d'origine", s_sig),
            Paragraph("Cachet et signature de l'établissement d'accueil", s_sig),
        ],
        ['\n\n\n\n', '\n\n\n\n', '\n\n\n\n'],
        [
            Paragraph("Date : ___________", s_sig),
            Paragraph("Date : ___________", s_sig),
            Paragraph("Date : ___________", s_sig),
        ],
    ], colWidths=[6*cm, 6*cm, 6*cm])
    sig.setStyle(TableStyle([
        ('BOX', (0,0), (0,-1), 0.5, colors.HexColor('#aaaaaa')),
        ('BOX', (1,0), (1,-1), 0.5, colors.HexColor('#aaaaaa')),
        ('BOX', (2,0), (2,-1), 0.5, colors.HexColor('#aaaaaa')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e8f0fb')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
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
        html = f"""<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;">
          <p>Bonjour,</p>
          <p>Voici votre mot de passe pour accéder aux réservations de mini-stages du <strong>{LYCEE['nom']}</strong> :</p>
          <div style="background:#f0f7ff;border:2px solid #1565c0;border-radius:8px;padding:20px;text-align:center;margin:20px 0;">
            <span style="font-size:30px;font-weight:bold;letter-spacing:8px;color:#1565c0;">{code}</span>
          </div>
          <p>Rendez-vous sur le site : <a href="{SITE_URL}">{SITE_URL}</a></p>
          <p><strong>Conservez ce mot de passe</strong> — il reste valable, inutile d'en redemander un nouveau à chaque fois.</p>
          <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
          <p style="color:#888;font-size:12px;">Ceci est un mail automatique, merci de ne pas y répondre. Pour nous contacter : ministagesfernandleger@gmail.com</p>
          <p style="color:#888;font-size:12px;">{LYCEE['nom']} — {LYCEE['adresse']}</p>
        </div>"""
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
        etab_email_direct = request.form.get('etab_email_affiche','').strip()
        resp_legal_email = request.form.get('resp_legal_email','').strip()
        contact_email = request.form.get('contact_email','').strip()
        resa = Reservation(
            code=code, creneau_id=cr.id,
            eleve_nom=request.form.get('eleve_nom','').strip().upper(),
            eleve_prenom=request.form.get('eleve_prenom','').strip(),
            eleve_classe=request.form.get('eleve_classe','').strip(),
            eleve_ddn=request.form.get('eleve_ddn','').strip(),
            resp_legal_nom=request.form.get('resp_legal_nom','').strip(),
            resp_legal_tel=request.form.get('resp_legal_tel','').strip(),
            resp_legal_email=resp_legal_email,
            etab_nom=request.form.get('etab_nom','').strip(),
            etab_ville=request.form.get('etab_ville','').strip(),
            etab_email=session['etab_email'],
            etab_email_direct=etab_email_direct,
            etab_contact=request.form.get('etab_contact','').strip(),
            etab_tel=request.form.get('etab_tel','').strip(),
            contact_nom=request.form.get('contact_nom','').strip(),
            contact_prenom=request.form.get('contact_prenom','').strip(),
            contact_tel=request.form.get('contact_tel','').strip(),
            contact_email=contact_email,
            remarques=request.form.get('remarques','').strip(),
        )
        db.session.add(resa)
        db.session.commit()
        pdf = generer_convention_pdf(resa)
        f = cr.formation
        nom_f = f"{f['niveau']} {f['nom']}" if f else cr.formation_id
        dest = destinataires_resa(resa)
        html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px;">
          <p>Bonjour,</p>
          <p>L'inscription au mini-stage du <strong>{LYCEE['nom']}</strong> est bien enregistrée.</p>
          <p>Votre code personnel pour modifier ou annuler le stage est : <strong style="color:#1565c0;font-size:1.1rem;letter-spacing:2px;">{code}</strong></p>
          <p>Site des mini-stages : <a href="{SITE_URL}">{SITE_URL}</a></p>
          <p>Vous trouverez, en pièce jointe, la convention. Elle doit être signée par le responsable légal et l'établissement d'origine (cachet + signature). L'élève devra être en possession de celle-ci le jour du stage.</p>
          <p><strong>Un élève sans convention signée ne pourra être accepté dans les locaux du lycée. Une réservation = un élève.</strong></p>
          <p>Il n'est pas nécessaire de la renvoyer avant. L'absence de nouvelle de notre part vaut acceptation du stage. L'élève se présentera 10 minutes avant l'heure prévue.</p>
          <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
          <p><strong>Élève :</strong> {resa.eleve_prenom} {resa.eleve_nom}</p>
          <p><strong>Informations sur le mini-stage :</strong></p>
          <ul>
            <li>Formation : {nom_f}</li>
            <li>Date : {date_fr(cr.date)}</li>
            <li>Horaires : {cr.heure_debut} – {cr.heure_fin}</li>
            <li>Salle : {cr.salle or '—'}</li>
            <li>Professeur référent : {cr.professeur or '—'}</li>
          </ul>
          <p><strong>Établissement d'origine :</strong></p>
          <ul>
            <li>Établissement : {resa.etab_nom}</li>
            <li>Contact : {resa.etab_contact or '—'}</li>
            <li>Téléphone : {resa.etab_tel or '—'}</li>
            <li>Email : {resa.etab_email}</li>
          </ul>
          <p><strong>Responsable légal :</strong></p>
          <ul>
            <li>Nom : {resa.resp_legal_nom or '—'}</li>
            <li>Téléphone : {resa.resp_legal_tel or '—'}</li>
          </ul>
          <p>Votre réservation a été réalisée le {date_fr(date.today())}. Nous vous remercions de l'intérêt porté à nos formations.</p>
          <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
          <p style="color:#888;font-size:12px;">Ceci est un mail automatique, merci de ne pas y répondre. Pour nous contacter : ministagesfernandleger@gmail.com</p>
          <p style="color:#888;font-size:12px;">{LYCEE['nom']} — {LYCEE['adresse']}</p>
        </div>"""
        envoyer_mail(dest, f"Confirmation mini-stage — {nom_f} le {date_fr(cr.date)}", html, [(f"convention_{code}.pdf", pdf)])
        envoyer_mail(MAIL_NOTIF, f"[NOUVELLE RÉSA] {nom_f} — {resa.eleve_prenom} {resa.eleve_nom} le {date_fr(cr.date)}", html, [(f"convention_{code}.pdf", pdf)])
        return redirect(url_for('confirmation', code=code))
    return render_template('reservation.html', formations=FORMATIONS, par_formation=par_formation, etab_email=session.get('etab_email'), date_fr=date_fr)

@app.route('/confirmation/<code>')
def confirmation(code):
    resa = Reservation.query.filter_by(code=code).first_or_404()
    return render_template('confirmation.html', resa=resa, date_fr=date_fr)

@app.route('/convention/<code>')
def telecharger_convention(code):
    resa = Reservation.query.filter_by(code=code).first_or_404()
    pdf = generer_convention_pdf(resa)
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=f"convention_{code}.pdf")

@app.route('/rgpd')
def rgpd():
    return render_template('rgpd.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/gerer', methods=['GET','POST'])
def gerer():
    resa = None
    erreur = None
    if request.method == 'POST':
        code = request.form.get('code','').strip().upper()
        resa = Reservation.query.filter_by(code=code, annulee=False).first()
        if not resa:
            erreur = "Code introuvable ou réservation déjà annulée."
    return render_template('gerer.html', resa=resa, erreur=erreur, creneaux_dispos=_creneaux_dispos_pour(resa) if resa else [])

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
    f = nouveau.formation
    nom_f = f"{f['niveau']} {f['nom']}" if f else ''
    dest = destinataires_resa(resa)
    html = f"""<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;">
      <p>Bonjour,</p>
      <p>Votre réservation <strong>{code}</strong> a été modifiée. Nouveau créneau : <strong>{nom_f}</strong> le {date_fr(nouveau.date)} de {nouveau.heure_debut} à {nouveau.heure_fin}.</p>
      <p>Une nouvelle convention vous est envoyée en pièce jointe.</p>
      <p style="color:#888;font-size:12px;">Ceci est un mail automatique. Pour nous contacter : ministagesfernandleger@gmail.com</p>
    </div>"""
    pdf = generer_convention_pdf(resa)
    envoyer_mail(dest, f"Modification réservation {code}", html, [(f"convention_{code}.pdf", pdf)])
    flash("Réservation modifiée. Une nouvelle convention vous a été envoyée.", "success")
    return redirect(url_for('gerer'))

@app.route('/annuler/<code>', methods=['POST'])
def annuler(code):
    resa = Reservation.query.filter_by(code=code, annulee=False).first_or_404()
    creneau_id = resa.creneau_id
    resa.annulee = True
    db.session.commit()
    cr = resa.creneau
    f = cr.formation
    nom_f = f"{f['niveau']} {f['nom']}" if f else ''
    dest = destinataires_resa(resa)
    html = f"""<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:30px;">
      <p>Bonjour,</p>
      <p>La réservation <strong>{code}</strong> ({resa.eleve_prenom} {resa.eleve_nom} — {nom_f} le {date_fr(cr.date)}) a bien été annulée.</p>
      <p style="color:#888;font-size:12px;">Ceci est un mail automatique. Pour nous contacter : ministagesfernandleger@gmail.com</p>
    </div>"""
    envoyer_mail(dest, f"Annulation réservation {code}", html)
    flash("Réservation annulée.", "success")
    return redirect(url_for('gerer'))

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
    return render_template('admin_dashboard.html', creneaux=creneaux, reservations=reservations, formations=FORMATIONS, today=date.today(), date_fr=date_fr)

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

def init_db():
    with app.app_context():
        db.create_all()

init_db()

if __name__ == '__main__':
    app.run(debug=True)
