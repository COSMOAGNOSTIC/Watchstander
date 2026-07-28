extends Node3D
## Real-vessel-shaped 3D blockout of USCG Cutter ACUSHNET / ex-USS SHACKLE
## (ARS-9). A companion to the live 2D visualizer (Main.tscn), NOT a
## replacement for it -- this is a static, non-networked "see the ship"
## view for demos and screenshots. Main.tscn is still the one that wires
## up to agent_core's WebSocket broadcaster and shows live deconfliction/
## HITL state; this scene doesn't listen for events at all.
##
## Sourced from docs/uscg-acushnet-ars9-source.md -- read that file for
## the full sourcing chain and the frame-range estimation caveat
## (+/-2-3 frames, tick-mark proximity, not digitized coordinates).
##
## Deliberate simplifications, spelled out here so nobody mistakes this
## for more than it is:
## - Hull is a straight-sided rectangular box (bow and stern squared
##   off). Real hull curvature exists on the source's Sheet 9 (Shell
##   Expansion) and is NOT traced here -- see source doc's "3D blockout
##   simplification" section for why that was a scope call, not an
##   oversight.
## - Every compartment box spans the full beam (port to starboard). The
##   source sheet shows port/starboard subdivisions for many spaces;
##   tracing each bulkhead was out of scope for this pass.
## - Frame position, compartment identity, and compartment order ARE
##   real. Hull shape and beam-wise subdivision are not.

const FEET_PER_FRAME := 1.94  # 213 ft overall / ~110 frames -- see source doc
const METERS_PER_FOOT := 0.3048
const FRAME_MAX := 110.0

const BEAM_M := 12.2  # ~40 ft beam
const DECK_HEIGHT_M := 2.7  # notional deck-to-deck height, not sourced
const HULL_DEPTH_M := 6.0  # notional, enough to visually contain 2 decks + margin

const HAZARD_COLOR := {
	"hot_work": Color("ff8c3c"),
	"confined_space": Color("aa78ff"),
	"working_aloft": Color("6edcff"),
	"fall_protection": Color("ffd25a"),
}
const FLAGGED_COLOR := Color("ff3b3b")
const HULL_COLOR := Color(0.55, 0.58, 0.62, 0.35)
const DECK_UNFLAGGED_COLOR := Color(0.35, 0.55, 0.75, 0.85)

# deck: 0 = Main Deck (upper), 1 = Second Deck (lower)
# All frame ranges read from docs/uscg-acushnet-ars9-source.md.
const COMPARTMENTS := [
	{"name": "Resistor Room (B-102-6E)", "deck": 0, "frame_start": 96, "frame_end": 104},
	{"name": "DC Shop (B-102-2Q)", "deck": 0, "frame_start": 90, "frame_end": 96},
	{"name": "Ship's Office (B-102-1Q)", "deck": 0, "frame_start": 86, "frame_end": 90},
	{"name": "Galley & Mess Deck (B-101-1L)", "deck": 0, "frame_start": 70, "frame_end": 86},
	{"name": "Chief's Mess (A-104-1L)", "deck": 0, "frame_start": 62, "frame_end": 70},
	{"name": "Jr. Officers Passage (A-103-6L)", "deck": 0, "frame_start": 40, "frame_end": 62},
	{"name": "Laundry (A-102-Q)", "deck": 0, "frame_start": 24, "frame_end": 40},
	{"name": "MAA Stores (A-101-A)", "deck": 0, "frame_start": 12, "frame_end": 24},
	{
		"name": "Anchor Windlass Room (A-102-E)", "deck": 0,
		"frame_start": 2, "frame_end": 12,
		"hazard": "fall_protection", "work_package_id": "FALL-2204",
	},
	{
		"name": "Main Deck, amidships (way of mast)", "deck": 0,
		"frame_start": 60, "frame_end": 70,
		"hazard": "working_aloft", "work_package_id": "ALOFT-2203",
	},
	{"name": "Lazarette (C-205-V)", "deck": 1, "frame_start": 100, "frame_end": 110},
	{"name": "Aft Steering (C-204-E)", "deck": 1, "frame_start": 92, "frame_end": 100},
	{"name": "Reefer Room (C-203-E)", "deck": 1, "frame_start": 84, "frame_end": 92},
	{
		"name": "Electric & Machine Shop (B-2)", "deck": 1,
		"frame_start": 70, "frame_end": 84,
		"hazard": "hot_work", "work_package_id": "HW-2201", "flagged": true,
	},
	{
		"name": "Electric & Machine Shop (B-2) -- confined space entry", "deck": 1,
		"frame_start": 74, "frame_end": 80,
		"hazard": "confined_space", "work_package_id": "CS-2202",
		"flagged": true, "inset": true,
	},
	{"name": "Generator Room (B-1)", "deck": 1, "frame_start": 58, "frame_end": 70},
	{"name": "Crew berthing", "deck": 1, "frame_start": 24, "frame_end": 58},
	{"name": "Forepeak Tank (A-1W)", "deck": 1, "frame_start": 2, "frame_end": 16},
]


func _ready() -> void:
	_build_hull()
	_build_compartments()
	_build_note()


func _frame_to_x(frame: float) -> float:
	var length_m := FRAME_MAX * FEET_PER_FRAME * METERS_PER_FOOT
	var pos_m := frame * FEET_PER_FRAME * METERS_PER_FOOT
	return pos_m - (length_m / 2.0)


func _build_hull() -> void:
	var length_m := FRAME_MAX * FEET_PER_FRAME * METERS_PER_FOOT
	var mesh := BoxMesh.new()
	mesh.size = Vector3(length_m, HULL_DEPTH_M, BEAM_M)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = HULL_COLOR
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mesh.material = mat
	var inst := MeshInstance3D.new()
	inst.mesh = mesh
	inst.position = Vector3(0, -DECK_HEIGHT_M * 0.5, 0)
	add_child(inst)


func _build_compartments() -> void:
	for c in COMPARTMENTS:
		var frame_start: float = c["frame_start"]
		var frame_end: float = c["frame_end"]
		var x_start := _frame_to_x(frame_start)
		var x_end := _frame_to_x(frame_end)
		var length: float = abs(x_end - x_start)
		var center_x: float = (x_start + x_end) / 2.0

		var deck_idx: int = c.get("deck", 0)
		var y := DECK_HEIGHT_M * 0.5 if deck_idx == 0 else -DECK_HEIGHT_M * 0.5
		var width := BEAM_M * 0.4 if c.get("inset", false) else BEAM_M * 0.92

		var mesh := BoxMesh.new()
		mesh.size = Vector3(max(length, 0.5), DECK_HEIGHT_M * 0.85, width)
		var mat := StandardMaterial3D.new()
		var hazard: String = c.get("hazard", "")
		if c.get("flagged", false):
			mat.albedo_color = FLAGGED_COLOR
			mat.emission_enabled = true
			mat.emission = FLAGGED_COLOR
			mat.emission_energy_multiplier = 0.6
		elif HAZARD_COLOR.has(hazard):
			mat.albedo_color = HAZARD_COLOR[hazard]
		else:
			mat.albedo_color = DECK_UNFLAGGED_COLOR
		mesh.material = mat

		var inst := MeshInstance3D.new()
		inst.mesh = mesh
		inst.position = Vector3(center_x, y, 0)
		add_child(inst)

		# Only label the hazard/flagged compartments -- labeling all ~17
		# compartments turned this into unreadable billboard soup at any
		# camera distance that also fits the whole hull in frame. The
		# plain compartments are still real, still positioned correctly,
		# just unlabeled in this static view (this is a "pretty picture"
		# demo view, not a technical schematic -- Main.tscn's 2D view is
		# the one that shows every package with live data).
		if c.get("flagged", false) or HAZARD_COLOR.has(hazard):
			var label := Label3D.new()
			label.text = c["name"]
			label.font_size = 44
			label.pixel_size = 0.035
			label.position = Vector3(center_x, y + DECK_HEIGHT_M * 0.55, width * 0.5 + 0.4)
			label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			label.modulate = Color.WHITE
			label.outline_size = 10
			add_child(label)


func _build_note() -> void:
	var label := Label3D.new()
	label.text = "USCGC ACUSHNET / ex-USS SHACKLE (ARS-9) -- simplified blockout, real frame positions\nsee docs/uscg-acushnet-ars9-source.md"
	label.font_size = 32
	label.pixel_size = 0.035
	label.position = Vector3(0, DECK_HEIGHT_M * 2.2, 0)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(label)
