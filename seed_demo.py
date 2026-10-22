"""
seed_demo.py — creates a demo college so you can try VIGNAN in 1 minute.

    python seed_demo.py          (add --reset to wipe and start over)

Creates:
  admin       / admin123      -> manages classrooms, subjects, faculty
  dr.rao      / faculty123    -> teaches Network Analysis (EIE 2-A)
  ms.lakshmi  / faculty123    -> teaches Python Programming (EIE 2-A)
  student     / student123    -> student of EIE 2nd Year – Section A

The sample PDFs below are short original notes written for this demo.
Replace them with your real faculty material.
"""

import os
import shutil
import sys

import pymupdf

import db
import ingest

DEMO_DIR = os.path.join(db.DATA_DIR, "demo_pdfs")

CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; }
h1 { font-size: 18pt; color: #1d3557; } h2 { font-size: 14pt; color: #1d3557; margin-top: 6pt; }
.f { font-family: monospace; background: #f1f1f1; } .muted { color: #666; font-size: 9pt; }
"""

# ------------------------------------------------------------------ content
NA_SYLLABUS = [
    """<h1>Network Analysis — Syllabus</h1>
<p class="muted">EIE, II Year I Semester · Course code 22EI3T02 (demo)</p>
<p><b>UNIT - I: Circuit Fundamentals</b><br>
Ohm's law, Kirchhoff's current law, Kirchhoff's voltage law, Mesh analysis, Nodal analysis, Source transformation</p>
<p><b>UNIT - II: Network Theorems</b><br>
Superposition theorem, Thevenin's theorem, Norton's theorem, Maximum power transfer theorem</p>
<p><b>UNIT - III: Transient Analysis</b><br>
RC circuit transient response, RL circuit transient response, Time constant</p>
<p><b>UNIT - IV: Resonance</b><br>
Series resonance, Quality factor, Bandwidth</p>
<p><b>UNIT - V: Two-Port Networks</b><br>
Z parameters, Y parameters, h parameters</p>
<p><b>TEXT BOOKS</b><br>1. Network Theory Lecture Notes (department).<br>2. Solved Problems in Circuit Analysis (department).</p>"""
]

NA_NOTES = [
    """<h1>Network Theory — Lecture Notes</h1><p class="muted">Prepared for EIE II Year (demo material)</p>
<h2>1. Ohm's Law and Circuit Elements</h2>
<p>Ohm's law states that the current through a conductor is directly proportional to the voltage across it,
provided temperature and other physical conditions remain constant. The constant of proportionality is the
resistance R, measured in ohms.</p><p class="f">V = I × R</p>
<p>A resistor dissipates energy as heat, with power P = V × I = I²R = V²/R. An inductor stores energy in a
magnetic field and opposes sudden changes in current, V = L di/dt. A capacitor stores energy in an electric
field and opposes sudden changes in voltage, I = C dv/dt.</p>""",
    """<h2>2. Kirchhoff's Laws</h2>
<p><b>Kirchhoff's Current Law (KCL):</b> the algebraic sum of currents entering a node is zero. In other
words, the total current entering a junction equals the total current leaving it. KCL follows from the
conservation of electric charge.</p><p class="f">Σ I_in = Σ I_out</p>
<p><b>Kirchhoff's Voltage Law (KVL):</b> the algebraic sum of all voltages around any closed loop (mesh) in a
circuit is zero. The voltage rises supplied by sources equal the voltage drops across the elements in the
loop. KVL follows from the conservation of energy.</p><p class="f">Σ V around a closed loop = 0</p>
<p>Sign convention: when moving around a loop, a drop from + to − across an element is taken as positive and a
rise from − to + is taken as negative (or the reverse, applied consistently).</p>""",
    """<h2>3. Mesh Analysis and Nodal Analysis</h2>
<p><b>Mesh analysis</b> applies KVL to every independent loop (mesh) of a planar circuit. A mesh current is
assumed in each mesh, usually clockwise, and one equation is written per mesh. Solving the simultaneous
equations gives the mesh currents. A circuit with b branches and n nodes has b − n + 1 independent meshes.</p>
<p><b>Nodal analysis</b> applies KCL at every node. One node is chosen as the reference (ground) and the
voltages of the remaining n − 1 nodes are the unknowns. Currents in each branch are written in terms of node
voltages using Ohm's law.</p>
<p><b>Source transformation:</b> a voltage source V in series with a resistance R can be replaced by a current
source I = V/R in parallel with the same R, and vice versa, without changing the behaviour at the terminals.</p>""",
    """<h2>4. Superposition Theorem</h2>
<p>In a linear bilateral network containing more than one independent source, the response (current or
voltage) in any element is the algebraic sum of the responses caused by each independent source acting alone,
with all other independent sources replaced by their internal resistances.</p>
<p>Procedure: (1) keep one source, (2) replace other voltage sources by short circuits and current sources by
open circuits, (3) find the response, (4) repeat for each source, (5) add all responses algebraically.</p>
<p>Superposition cannot be used directly to compute power, because power is a non-linear (square) function of
current or voltage.</p>""",
    """<h2>5. Thevenin's Theorem and Norton's Theorem</h2>
<p><b>Thevenin's theorem:</b> any linear two-terminal network can be replaced by an equivalent circuit made of
a single voltage source V_th in series with a single resistance R_th.</p>
<p>V_th is the open-circuit voltage across the load terminals. R_th is the resistance seen from the load
terminals with all independent sources replaced by their internal resistances (voltage sources shorted,
current sources opened).</p><p class="f">I_L = V_th / (R_th + R_L)</p>
<p><b>Norton's theorem:</b> the same network can also be replaced by a current source I_N in parallel with a
resistance R_N. I_N is the short-circuit current through the load terminals and R_N = R_th.
The two equivalents are related by V_th = I_N × R_th.</p>""",
    """<h2>6. Maximum Power Transfer Theorem</h2>
<p>A linear network delivers maximum power to a load resistance R_L when the load resistance equals the
Thevenin resistance of the network as seen from the load terminals.</p><p class="f">Condition: R_L = R_th</p>
<p class="f">P_max = V_th² / (4 R_th)</p>
<p>At maximum power transfer the efficiency is only 50 %, because equal power is dissipated in R_th. This is why
power systems are not operated at the maximum power transfer condition, while communication circuits often
are.</p>""",
    """<h2>7. Transient Analysis of RC and RL Circuits</h2>
<p>When a switch is opened or closed, currents and voltages take some time to settle to new steady values. This
period is called the transient.</p>
<p><b>RC circuit (charging):</b> when a DC voltage V is applied to a series RC circuit, the capacitor voltage rises
exponentially: v_C(t) = V (1 − e^(−t/RC)). The time constant τ = RC is the time taken for the capacitor
voltage to reach 63.2 % of its final value.</p>
<p><b>RL circuit:</b> when a DC voltage V is applied to a series RL circuit, the current rises as
i(t) = (V/R)(1 − e^(−Rt/L)). The time constant is τ = L/R.</p>
<p>After about five time constants (5τ) the transient is considered complete and the circuit is in steady
state.</p>""",
    """<h2>8. Series Resonance</h2>
<p>A series RLC circuit is at resonance when the inductive reactance equals the capacitive reactance
(X_L = X_C). The impedance is then minimum and purely resistive (Z = R), so the current is maximum and in phase
with the voltage.</p><p class="f">f_r = 1 / (2π √(LC))</p>
<p><b>Quality factor:</b> Q = (1/R) √(L/C) = ω_r L / R. Q measures the sharpness of resonance; at resonance the
voltage across L or C is Q times the supply voltage (voltage magnification).</p>
<p><b>Bandwidth:</b> BW = f₂ − f₁ = f_r / Q, where f₁ and f₂ are the half-power frequencies at which the
current falls to 0.707 of its maximum value.</p>""",
    """<h2>9. Two-Port Networks</h2>
<p>A two-port network has an input port (V₁, I₁) and an output port (V₂, I₂). Its behaviour is described by
parameter sets that relate these four quantities.</p>
<p><b>Z parameters (open-circuit impedance parameters):</b> V₁ = Z₁₁I₁ + Z₁₂I₂ and V₂ = Z₂₁I₁ + Z₂₂I₂. They are
measured by open-circuiting one port at a time.</p>
<p><b>Y parameters (short-circuit admittance parameters):</b> I₁ = Y₁₁V₁ + Y₁₂V₂ and I₂ = Y₂₁V₁ + Y₂₂V₂, measured
by short-circuiting one port at a time. Y = Z⁻¹.</p>
<p><b>h parameters (hybrid parameters):</b> V₁ = h₁₁I₁ + h₁₂V₂ and I₂ = h₂₁I₁ + h₂₂V₂. They are widely used
to model transistors.</p>""",
]

NA_WORKBOOK = [
    """<h1>Solved Problems in Circuit Analysis</h1><p class="muted">Department problem book (demo material)</p>
<h2>Problem 1 — Finding a Thevenin equivalent</h2>
<p>A 12 V source in series with 4 Ω is connected across a 6 Ω resistor; the load is connected across the 6 Ω
resistor. Find the Thevenin equivalent seen by the load.</p>
<p><b>Solution:</b> Open-circuit voltage by voltage division: V_th = 12 × 6/(4 + 6) = 7.2 V. With the source
shorted, R_th = 4 ∥ 6 = 2.4 Ω. So the network reduces to 7.2 V in series with 2.4 Ω. For maximum power the
load should be 2.4 Ω and P_max = 7.2²/(4 × 2.4) = 5.4 W.</p>""",
    """<h2>Problem 2 — KVL in a single loop</h2>
<p>A 10 V battery drives three series resistors of 1 Ω, 2 Ω and 2 Ω. Find the loop current and each drop.</p>
<p><b>Solution:</b> Applying KVL around the loop: 10 − 1·I − 2·I − 2·I = 0, so I = 2 A. The drops are 2 V, 4 V
and 4 V, which add up to the 10 V supply, confirming KVL.</p>
<h2>Problem 3 — RC time constant</h2>
<p>A 100 kΩ resistor and a 10 µF capacitor are charged from 5 V. Find the time constant and the capacitor
voltage after one time constant.</p>
<p><b>Solution:</b> τ = RC = 100×10³ × 10×10⁻⁶ = 1 s. After one time constant v_C = 5(1 − e⁻¹) = 3.16 V,
that is 63.2 % of 5 V. The capacitor is practically fully charged after 5 s.</p>""",
]

PY_SYLLABUS = [
    """<h1>Python Programming — Syllabus</h1><p class="muted">II Year · demo</p>
<p><b>UNIT - I: Python Basics</b><br>Data types, Variables, Operators, Conditional statements, Loops</p>
<p><b>UNIT - II: Data Structures</b><br>Lists, Tuples, Dictionaries, Sets, List comprehension</p>
<p><b>UNIT - III: Functions and Modules</b><br>Functions, Lambda functions, Recursion, Modules and packages</p>
<p><b>UNIT - IV: Files and Exceptions</b><br>File handling, Exception handling</p>
<p><b>UNIT - V: Object Oriented Programming</b><br>Classes and objects, Inheritance, Polymorphism</p>
<p><b>TEXT BOOKS</b><br>1. Python Lab Notes (department).</p>"""
]

PY_NOTES = [
    """<h1>Python Lab Notes</h1>
<h2>1. Data types, variables and loops</h2>
<p>Python's basic data types are int, float, complex, bool and str. A variable is created when a value is first
assigned to it; Python is dynamically typed, so the type belongs to the value, not the variable.</p>
<p>Conditional statements use if, elif and else. A for loop iterates over any sequence, for example
<span class="f">for i in range(5):</span>, while a while loop repeats as long as its condition is true. break exits
a loop early and continue skips to the next iteration.</p>""",
    """<h2>2. Lists, tuples, dictionaries and sets</h2>
<p>A <b>list</b> is an ordered, mutable sequence: <span class="f">marks = [78, 91, 66]</span>. A <b>tuple</b> is an
ordered but immutable sequence, written with parentheses. A <b>dictionary</b> stores key–value pairs with fast
lookup by key: <span class="f">student = {"roll": 17, "branch": "EIE"}</span>. A <b>set</b> is an unordered
collection of unique items, useful for removing duplicates and for membership tests.</p>
<p><b>List comprehension</b> builds a list in one line: <span class="f">squares = [x*x for x in range(10) if x % 2 == 0]</span>.</p>""",
    """<h2>3. Functions, lambda and recursion</h2>
<p>A function is defined with def, takes parameters and may return a value. Default arguments, keyword
arguments, *args and **kwargs make functions flexible.</p>
<p>A <b>lambda function</b> is a small anonymous function written in one expression, e.g.
<span class="f">square = lambda x: x * x</span>, often used with map, filter and sorted.</p>
<p><b>Recursion</b> is when a function calls itself. Every recursive function needs a base case to stop, e.g.
factorial(n) = n × factorial(n − 1) with factorial(0) = 1.</p>
<p>A <b>module</b> is a .py file whose functions can be imported; a <b>package</b> is a folder of modules.</p>""",
    """<h2>4. File handling and exception handling</h2>
<p>Files are opened with open(path, mode); common modes are "r" (read), "w" (write, overwrites) and "a"
(append). The with statement closes the file automatically: <span class="f">with open("data.txt") as f: text = f.read()</span>.</p>
<p><b>Exception handling</b> uses try, except, else and finally. Code that may fail goes in try; except catches a
specific error such as ZeroDivisionError or FileNotFoundError; finally always runs, which makes it the right place
for clean-up code.</p>""",
    """<h2>5. Object oriented programming</h2>
<p>A <b>class</b> is a blueprint and an <b>object</b> is an instance of it. The __init__ method (constructor)
initialises attributes, and self refers to the current object.</p>
<p><b>Inheritance</b> lets a child class reuse and extend a parent class: <span class="f">class Sensor(Device):</span>.
<b>Polymorphism</b> means the same method name behaves differently for different classes, for example each
sensor class implementing its own read() method.</p>""",
]


# ------------------------------------------------------------------ helpers
def make_pdf(path, pages_html):
    doc = pymupdf.open()
    for html in pages_html:
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 800), html, css=CSS)
    doc.save(path)
    doc.close()


def upload(subject_id, title, kind, filename, pages_html, faculty_id):
    path = os.path.join(DEMO_DIR, filename)
    make_pdf(path, pages_html)
    with open(path, "rb") as f:
        rep = ingest.add_pdf(subject_id, title, kind, filename, f.read(), faculty_id)
    print(f"  + {title}: {rep['pages']} pages, {rep['chunks']} chunks")


def main():
    if "--reset" in sys.argv and os.path.exists(db.DATA_DIR):
        shutil.rmtree(db.DATA_DIR)
    db.init()
    if db.username_exists("admin"):
        print("Demo data already exists. Run `python seed_demo.py --reset` to recreate it.")
        return
    os.makedirs(DEMO_DIR, exist_ok=True)

    db.create_user("admin", "College Admin", "admin123", "admin")
    eie_a = db.create_classroom("EIE", 2, "A")
    db.create_classroom("EIE", 2, "B")
    db.create_classroom("CSE", 2, "A")

    rao = db.create_user("dr.rao", "Dr. K. Rao", "faculty123", "faculty")
    lak = db.create_user("ms.lakshmi", "Ms. P. Lakshmi", "faculty123", "faculty")
    db.create_user("student", "Demo Student", "student123", "student", eie_a)

    na = db.create_subject(eie_a, "Network Analysis", "22EI3T02", rao)
    py = db.create_subject(eie_a, "Python Programming", "22CS3L05", lak)

    print("Uploading demo material...")
    upload(na, "Network Analysis Syllabus", "syllabus", "na_syllabus.pdf", NA_SYLLABUS, rao)
    upload(na, "Network Theory Lecture Notes", "notes", "network_theory_notes.pdf", NA_NOTES, rao)
    upload(na, "Solved Problems in Circuit Analysis", "textbook", "circuit_problems.pdf", NA_WORKBOOK, rao)
    upload(py, "Python Programming Syllabus", "syllabus", "py_syllabus.pdf", PY_SYLLABUS, lak)
    upload(py, "Python Lab Notes", "notes", "python_lab_notes.pdf", PY_NOTES, lak)

    db.post_announcement(na, rao, "Mid-1 covers Units I and II. Focus on Thevenin and maximum power transfer problems.")
    db.post_announcement(py, lak, "Lab record submission this Friday. Bring printed programs for Unit II.")
    print("\nDone! Run:  streamlit run app.py")
    print("Logins: student/student123 · dr.rao/faculty123 · admin/admin123")


if __name__ == "__main__":
    main()
