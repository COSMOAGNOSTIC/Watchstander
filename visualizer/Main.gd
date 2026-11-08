extends Node2D
##
## Real-time spatial visualizer for Watchstander.
##
## Watchstander's work packages carry spatial metadata -- frame range and
## deck level -- so this scene places each package on a schematic of the
## NOTIONAL carrier (case_data/carrier_notional_v1.json): a procedural
## blueprint background (assets/gen_assets.py), not a drawing of any real
## ship (AGENTS.md rule 6; ADR-049). See ARCHITECTURE.md Section 8.
##
## Connects to the WebSocket server agent_core.events opens on
## ws://127.0.0.1:8081 (a different port than cosmoai-adept's 8080, so
## both visualizers can run side by side). Uses the literal loopback
## address, not the hostname "localhost" -- on a dual-stack machine
## (Windows in particular) "localhost" can resolve to a different address
## family on the Python server side than on this client side, so both
## sockets open successfully and neither errors, but no data ever
## crosses. See agent_core/events.py and ARCHITECTURE.md ADR-026.
##
## One view today. VIEWS stays a list, and V still cycles it, so another
## notional view can be added without touching the drawing code.

const RECONNECT_INTERVAL := 2.0
const MIN_BUBBLE_TIME := 3.0   # seconds - even a short status needs to be readable
const MAX_BUBBLE_TIME := 7.0
const CHARS_PER_SECOND := 12.0

# Per-view pixel calibration. The schematic is 960x540 with deck lines at
# y = 60/160/260/360/460 (assets/gen_assets.py); markers sit mid-band. The
# notional carrier's frames run 0-260, laid out left to right after the band
# labels. Positions are illustrative, not to scale.
const VIEWS := [
	{
		"name": "Notional schematic",
		"texture": "res://assets/bg_blueprint.png",
		"bg_position": Vector2(0, 0),
		"bg_size": Vector2(960, 540),
		"frame_min": 0.0, "frame_max": 260.0,
		"x_min": 250.0, "x_max": 940.0,
		"band_aloft": 110.0,
		"band_main_deck": 210.0,
		"band_2nd_deck": 310.0,
		"band_3rd_deck": 410.0,
		"band_over_side": 500.0,
		"label_y": {
			"ALOFT / STAGING": 68.0,
			"MAIN DECK": 168.0,
			"2ND DECK": 268.0,
			"3RD DECK / HOLD": 368.0,
			"OVER THE SIDE (WATERLINE)": 468.0,
		},
		"review_station": Vector2(480, 488),
	},
]

# Okabe-Ito colorblind-safe qualitative palette (Okabe & Ito, 2008 --
# the standard reference palette for figures that must stay distinguishable
# under the common forms of color vision deficiency), added 2026-08-08
# (ARCHITECTURE.md ADR-028) to replace the original pastel/light palette,
# which was tuned for the dark procedural schematic background and reads
# poorly against the real print's white/cream paper -- reported directly
# ("the color palette is wrong and hard to see on a white background").
# ADR-049: the background is the dark schematic again; these hues still read
# on it, and the default marker color was switched to light grey.
const HAZARD_COLOR := {
	"hot_work": Color("d55e00"),        # vermillion
	"confined_space": Color("0072b2"),  # blue
	"working_aloft": Color("009e73"),   # bluish green
	"fall_protection": Color("e69f00"), # orange
	"over_the_side": Color("cc79a7"),   # reddish purple
}
const DEFAULT_MARKER_COLOR := Color("d8e2ec")  # light grey: legible on the dark schematic
const CONFLICT_COLOR := Color("d0021b")  # saturated safety red, distinct from the vermillion above

var active_view := 0

var socket := WebSocketPeer.new()
var reconnect_timer := 0.0
var connected := false
var status_label: Label
var view_hint_label: Label

var bg_node: TextureRect
var band_label_nodes := {}  # text -> Label

var markers := {}          # work_package_id -> Node2D
var marker_base_color := {} # work_package_id -> Color
var conflict_lines: Array[Line2D] = []
var band_placements: Array = []  # [{x1, x2, band_y, offset}] -- for de-stacking overlapping ranges

var bubble_panel: PanelContainer
var bubble_label: Label
var bubble_timer := 0.0

var review_glow: Sprite2D
var review_label: Label
var review_pulsing := false
var review_pulse_t := 0.0

# Replayed on view toggle so switching angles mid-scene re-lays-out the
# same data against the new view's calibration instead of losing it.
var last_work_packages: Array = []
var last_conflicts: Array = []
var hitl_awaiting_id := ""
var hitl_awaiting_provenance := ""


func _ready() -> void:
	RenderingServer.set_default_clear_color(Color("0a1626"))
	_build_background()
	_build_band_labels()
	_build_review_station()
	_build_bubble()
	_build_hud_text()
	_connect_socket()


func _current_view() -> Dictionary:
	return VIEWS[active_view]


func _build_background() -> void:
	# The background for the active view, at its natural pixel size
	# (pre-scaled once when the asset was prepared, not resized at
	# runtime, so there's no distortion between this and the calibration
	# constants above). Positioned with margin on all sides for the band
	# labels and HUD text drawn on top of it.
	var view := _current_view()
	bg_node = TextureRect.new()
	bg_node.texture = load(view["texture"])
	bg_node.position = view["bg_position"]
	bg_node.size = view["bg_size"]
	bg_node.z_index = -10
	add_child(bg_node)


func _build_band_labels() -> void:
	var view := _current_view()
	for text in view["label_y"].keys():
		var label := Label.new()
		label.text = text
		label.position = Vector2(8, view["label_y"][text])
		label.add_theme_color_override("font_color", Color("5a8cb4"))
		add_child(label)
		band_label_nodes[text] = label


# Idle vs. pulsing alpha for the Safety Review station glow. Idle stays
# faint (not invisible -- the station still needs to be findable before
# anything is ever flagged) rather than the same visibility as the
# pulsing "awaiting a real decision" state, which otherwise reads as
# noise: a review station that looks the same whether something is
# actually pending or not was reported as confusing ("I don't think
# you're mapping anything logically to this") when nothing had loaded yet.
# Tuned for the crisp marker_pin.png (ADR-028) -- these were originally
# tuned for glow_sprite.png's soft blur (idle 0.12, active-base 0.4) and
# read too faint once the marker became a solid opaque pin instead.
const REVIEW_GLOW_IDLE_ALPHA := 0.35
const REVIEW_GLOW_ACTIVE_BASE_ALPHA := 0.55

func _build_review_station() -> void:
	var view := _current_view()
	var glow := Sprite2D.new()
	glow.texture = load("res://assets/marker_pin.png")
	glow.position = view["review_station"]
	glow.modulate = Color(0.9, 0.6, 0.25, REVIEW_GLOW_IDLE_ALPHA)
	glow.scale = Vector2(0.5, 0.5)
	add_child(glow)
	review_glow = glow

	var label := Label.new()
	label.text = "SAFETY REVIEW (HITL)"
	label.add_theme_color_override("font_color", Color("ffb96b"))
	label.position = view["review_station"] + Vector2(-70, 26)
	label.size = Vector2(140, 20)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(label)
	review_label = label


func _build_bubble() -> void:
	bubble_panel = PanelContainer.new()
	bubble_panel.visible = false
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.03, 0.07, 0.12, 0.94)
	style.border_color = Color("5a8cb4")
	style.border_width_left = 2
	style.border_width_right = 2
	style.border_width_top = 2
	style.border_width_bottom = 2
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 8
	style.content_margin_bottom = 8
	bubble_panel.add_theme_stylebox_override("panel", style)
	bubble_panel.custom_minimum_size = Vector2(560, 0)
	bubble_panel.position = Vector2(200, 8)

	bubble_label = Label.new()
	bubble_label.autowrap_mode = TextServer.AUTOWRAP_WORD
	bubble_label.add_theme_color_override("font_color", Color("cfe6ff"))
	bubble_panel.add_child(bubble_label)
	add_child(bubble_panel)


func _build_hud_text() -> void:
	var title := Label.new()
	title.text = "WATCHSTANDER // SPATIAL DECONFLICTION"
	title.position = Vector2(200, -18)
	title.add_theme_color_override("font_color", Color("6edcff"))
	add_child(title)

	status_label = Label.new()
	status_label.text = "connecting to ws://127.0.0.1:8081 ..."
	status_label.position = Vector2(16, 516)
	status_label.add_theme_color_override("font_color", Color("3a5a78"))
	add_child(status_label)

	view_hint_label = Label.new()
	view_hint_label.text = "view: %s  (press V to switch)" % _current_view()["name"]
	view_hint_label.position = Vector2(16, 534)
	view_hint_label.add_theme_color_override("font_color", Color("5a8cb4"))
	add_child(view_hint_label)


func _connect_socket() -> void:
	var err := socket.connect_to_url("ws://127.0.0.1:8081")
	if err != OK:
		push_warning("visualizer: could not start connection: %s" % err)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_V:
			_toggle_view()


func _toggle_view() -> void:
	active_view = (active_view + 1) % VIEWS.size()
	var view := _current_view()

	bg_node.texture = load(view["texture"])
	bg_node.position = view["bg_position"]
	bg_node.size = view["bg_size"]

	for text in band_label_nodes.keys():
		if view["label_y"].has(text):
			band_label_nodes[text].position = Vector2(8, view["label_y"][text])

	review_glow.position = view["review_station"]
	review_label.position = view["review_station"] + Vector2(-70, 26)

	if view_hint_label:
		view_hint_label.text = "view: %s  (press V to switch)" % view["name"]

	_rebuild_markers_for_current_view()


func _rebuild_markers_for_current_view() -> void:
	# Re-lays-out the same replayed data against the newly-active view's
	# calibration -- a toggle mid-scene shouldn't lose what's on screen,
	# it should show the same flagged packages from a different angle.
	for id in markers.keys():
		markers[id].queue_free()
	markers.clear()
	marker_base_color.clear()
	for line in conflict_lines:
		line.queue_free()
	conflict_lines.clear()
	band_placements.clear()

	for wp in last_work_packages:
		_spawn_marker(wp)

	var seen := {}
	for c in last_conflicts:
		_flag_conflict(c, seen)

	if hitl_awaiting_id != "":
		_draw_hitl_line(hitl_awaiting_id)


func _process(delta: float) -> void:
	socket.poll()
	var state := socket.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if not connected:
			connected = true
			if status_label:
				status_label.text = "connected: ws://127.0.0.1:8081"
				status_label.add_theme_color_override("font_color", Color("6effbe"))
		while socket.get_available_packet_count() > 0:
			var packet := socket.get_packet().get_string_from_utf8()
			_handle_event(packet)
	elif state == WebSocketPeer.STATE_CLOSED:
		if connected:
			connected = false
		if status_label:
			status_label.text = "not connected -- retrying ws://127.0.0.1:8081 ..."
			status_label.add_theme_color_override("font_color", Color("ff8c3c"))
		reconnect_timer -= delta
		if reconnect_timer <= 0.0:
			reconnect_timer = RECONNECT_INTERVAL
			_connect_socket()

	if bubble_panel.visible:
		bubble_timer -= delta
		if bubble_timer <= 0.0:
			bubble_panel.visible = false

	if review_pulsing and review_glow:
		review_pulse_t += delta * 4.0
		review_glow.modulate.a = REVIEW_GLOW_ACTIVE_BASE_ALPHA + 0.3 * abs(sin(review_pulse_t))


func _handle_event(raw: String) -> void:
	var parsed = JSON.parse_string(raw)
	if parsed == null or typeof(parsed) != TYPE_DICTIONARY:
		return

	var event_type: String = parsed.get("type", "")
	match event_type:
		"deconfliction_start":
			_clear_scene()
			var packages: Array = parsed.get("work_packages", [])
			last_work_packages = packages
			last_conflicts = []
			hitl_awaiting_id = ""
			for wp in packages:
				_spawn_marker(wp)
			_say("scanning %d work package(s) for spatial conflicts..." % packages.size())
		"deconfliction_result":
			var conflicts: Array = parsed.get("conflicts", [])
			last_conflicts = conflicts
			if conflicts.is_empty():
				_say("no conflicts detected -- all work packages clear")
			else:
				var seen := {}
				for c in conflicts:
					_flag_conflict(c, seen)
				_say("%d work package(s) flagged for conflict" % conflicts.size())
		"reasoning_start":
			_say("synthesizing safety brief(s)...")
		"reasoning_result":
			var briefs: Array = parsed.get("briefs", [])
			for b in briefs:
				_say("brief ready: %s %s" % [b.get("work_package_id", ""), b.get("provenance", "")])
		"awaiting_approval", "hitl_awaiting":
			var wp_id: String = parsed.get("work_package_id", "")
			var provenance: String = parsed.get("safety_brief_provenance", "")
			hitl_awaiting_id = wp_id
			hitl_awaiting_provenance = provenance
			review_pulsing = true
			_draw_hitl_line(wp_id)
			_say("SAFETY REVIEW: %s awaiting human decision %s" % [wp_id, provenance])
		"approval_decided", "hitl_decided":
			hitl_awaiting_id = ""
			review_pulsing = false
			if review_glow:
				review_glow.modulate.a = REVIEW_GLOW_IDLE_ALPHA
			# "decision" (cosmoai-adept's approval_decided) carried a raw
			# human-readable string; Watchstander's hitl_decided instead
			# broadcasts the structured "disposition" (approved/rejected/
			# invalid) per events.py's ids-and-flags-only broadcast policy --
			# check both so this scene can render either event type.
			var decision: String = parsed.get("decision", parsed.get("disposition", parsed.get("approved", "")))
			_say("%s decision: %s" % [parsed.get("work_package_id", ""), decision])


func _draw_hitl_line(wp_id: String) -> void:
	if not markers.has(wp_id):
		return
	var m: Node2D = markers[wp_id]
	var line := Line2D.new()
	line.width = 2.0
	line.default_color = Color("ffb96b")
	line.points = PackedVector2Array([m.position, _current_view()["review_station"]])
	add_child(line)
	conflict_lines.append(line)


func _clear_scene() -> void:
	for id in markers.keys():
		markers[id].queue_free()
	markers.clear()
	marker_base_color.clear()
	for line in conflict_lines:
		line.queue_free()
	conflict_lines.clear()
	band_placements.clear()
	review_pulsing = false
	if review_glow:
		review_glow.modulate.a = REVIEW_GLOW_IDLE_ALPHA


func _frame_to_x(frame) -> float:
	var view := _current_view()
	var frame_min: float = view["frame_min"]
	var frame_max: float = view["frame_max"]
	var x_min: float = view["x_min"]
	var x_max: float = view["x_max"]
	if frame == null:
		return (x_min + x_max) / 2.0
	var f: float = clamp(float(frame), frame_min, frame_max)
	return x_min + (f - frame_min) / (frame_max - frame_min) * (x_max - x_min)


func _band_y_for(wp: Dictionary) -> float:
	var view := _current_view()
	if wp.get("is_aloft", false):
		return view["band_aloft"]
	if wp.get("is_over_side", false):
		return view["band_over_side"]
	var deck: String = str(wp.get("deck_level", "")).to_lower()
	if deck.find("2nd") != -1 or deck.find("second") != -1:
		return view["band_2nd_deck"]
	if deck.find("3rd") != -1 or deck.find("third") != -1 or deck.find("hold") != -1 or deck.find("4th") != -1 or deck.find("5th") != -1:
		return view["band_3rd_deck"]
	return view["band_main_deck"]


func _spawn_marker(wp: Dictionary) -> void:
	var id: String = wp.get("work_package_id", "")
	var hazards: Array = wp.get("hazard_categories", [])
	var color: Color = DEFAULT_MARKER_COLOR
	if hazards.size() > 0 and HAZARD_COLOR.has(hazards[0]):
		color = HAZARD_COLOR[hazards[0]]

	var band_y := _band_y_for(wp)
	var x1 := _frame_to_x(wp.get("frame_start", null))
	var x2 := _frame_to_x(wp.get("frame_end", null))
	if x2 < x1:
		var tmp := x1
		x1 = x2
		x2 = tmp

	# De-stack: if this range overlaps an already-placed marker on the same
	# band, shift down so labels/bars stay legible instead of printing on
	# top of each other -- this is exactly the situation a flagged conflict
	# produces (two packages sharing frames and a deck level).
	var stack_offset := 0.0
	for placed in band_placements:
		if placed["band_y"] == band_y and x1 <= placed["x2"] and placed["x1"] <= x2:
			stack_offset = max(stack_offset, placed["offset"] + 20.0)
	band_placements.append({"x1": x1, "x2": x2, "band_y": band_y, "offset": stack_offset})

	var y := band_y + stack_offset
	var node := Node2D.new()
	node.position = Vector2((x1 + x2) / 2.0, y)
	add_child(node)

	# Frame-range bar showing the work package's spatial extent. Alpha
	# raised from the original 0.55 (tuned for a dark background, washed
	# out against white paper) to 0.85.
	var bar := Line2D.new()
	bar.width = 6.0
	bar.default_color = Color(color.r, color.g, color.b, 0.85)
	bar.points = PackedVector2Array([Vector2(x1 - node.position.x, 0), Vector2(x2 - node.position.x, 0)])
	node.add_child(bar)

	# Crisp opaque marker pin (ADR-028), not the old soft glow_sprite blur
	# -- see gen_assets.py's marker_pin() docstring for why. Child index 1
	# (after the bar, before the label) -- _flag_conflict() below reaches
	# this same sprite by that fixed index, so the child order here has to
	# stay bar/pin/label.
	var pin := Sprite2D.new()
	pin.texture = load("res://assets/marker_pin.png")
	pin.modulate = color
	pin.scale = Vector2(0.32, 0.32)
	node.add_child(pin)

	# Label text stays a fixed dark color with a white outline, not the
	# hazard color itself -- some hazard colors in the new palette (e.g.
	# the orange/vermillion pair) are close enough to each other, and
	# close enough to some of the drawing's own printed ink, that colored
	# text alone was hard to read reliably against white paper. The
	# colored marker dot above already carries the hazard-category
	# encoding; the label's job is just to be legible.
	var label := Label.new()
	label.text = id
	label.add_theme_color_override("font_color", Color("1a1a1a"))
	label.add_theme_color_override("font_outline_color", Color("ffffff"))
	label.add_theme_constant_override("outline_size", 4)
	label.position = Vector2(-40, -28)
	label.size = Vector2(80, 16)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_child(label)

	markers[id] = node
	marker_base_color[id] = color


func _flag_conflict(conflict: Dictionary, seen: Dictionary) -> void:
	var id: String = conflict.get("work_package_id", "")
	if markers.has(id):
		var sprite := markers[id].get_child(1) as Sprite2D  # pin is child index 1 (bar, pin, label)
		if sprite:
			sprite.modulate = Color(CONFLICT_COLOR.r, CONFLICT_COLOR.g, CONFLICT_COLOR.b, 0.85)

	for other_id in conflict.get("conflicts_with", []):
		var pair_key := "-".join([id, other_id]) if id < other_id else "-".join([other_id, id])
		if seen.has(pair_key):
			continue
		seen[pair_key] = true
		if markers.has(id) and markers.has(other_id):
			var line := Line2D.new()
			line.width = 3.0
			line.default_color = CONFLICT_COLOR
			line.points = PackedVector2Array([markers[id].position, markers[other_id].position])
			add_child(line)
			conflict_lines.append(line)


func _say(text: String) -> void:
	bubble_label.text = text
	bubble_panel.visible = true
	bubble_timer = clamp(text.length() / CHARS_PER_SECOND, MIN_BUBBLE_TIME, MAX_BUBBLE_TIME)
