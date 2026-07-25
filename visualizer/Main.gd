extends Node2D
##
## Real-time spatial visualizer for Watchstander -- "Blueprint" skin.
##
## Unlike cosmoai-adept's visualizer (an agent walking between abstract
## tool stations), Watchstander's work packages already carry real
## spatial metadata -- frame range and deck level -- so this scene
## renders an actual schematic shipyard/vessel cross-section rather than
## an abstraction layered on top of unrelated data. See ARCHITECTURE.md
## Section 8.
##
## Connects to the WebSocket server agent_core.events opens on
## ws://localhost:8081 (a different port than cosmoai-adept's 8080, so
## both visualizers can run side by side).

const RECONNECT_INTERVAL := 2.0
const MIN_BUBBLE_TIME := 3.0   # seconds - even a short status needs to be readable
const MAX_BUBBLE_TIME := 7.0
const CHARS_PER_SECOND := 12.0

const FRAME_MIN := 0.0
const FRAME_MAX := 200.0
const X_MIN := 60.0
const X_MAX := 900.0

# Deck-level band centers, top to bottom -- matches the horizontal lines
# baked into assets/bg_blueprint.png at y = 60, 160, 260, 360, 460.
const BAND_ALOFT := 110.0
const BAND_MAIN_DECK := 210.0
const BAND_2ND_DECK := 310.0
const BAND_3RD_DECK := 410.0
const BAND_OVER_SIDE := 490.0

const SAFETY_REVIEW_STATION := Vector2(480, 478)

const HAZARD_COLOR := {
	"hot_work": Color("ff8c3c"),
	"confined_space": Color("aa78ff"),
	"working_aloft": Color("6edcff"),
	"fall_protection": Color("ffd25a"),
	"over_the_side": Color("6effbe"),
}
const DEFAULT_MARKER_COLOR := Color("cfe6ff")
const CONFLICT_COLOR := Color("ff4646")

var socket := WebSocketPeer.new()
var reconnect_timer := 0.0
var connected := false

var markers := {}          # work_package_id -> Node2D
var marker_base_color := {} # work_package_id -> Color
var conflict_lines: Array[Line2D] = []
var band_placements: Array = []  # [{x1, x2, band_y, offset}] -- for de-stacking overlapping ranges

var bubble_panel: PanelContainer
var bubble_label: Label
var bubble_timer := 0.0

var review_glow: Sprite2D
var review_pulsing := false
var review_pulse_t := 0.0


func _ready() -> void:
	RenderingServer.set_default_clear_color(Color("0a1626"))
	_build_background()
	_build_band_labels()
	_build_review_station()
	_build_bubble()
	_build_hud_text()
	_connect_socket()


func _build_background() -> void:
	var bg := TextureRect.new()
	bg.texture = load("res://assets/bg_blueprint.png")
	bg.size = Vector2(960, 540)
	bg.z_index = -10
	add_child(bg)


func _build_band_labels() -> void:
	var labels := {
		"ALOFT / STAGING": 65.0,
		"MAIN DECK": 165.0,
		"2ND DECK": 265.0,
		"3RD DECK / HOLD": 365.0,
		"OVER THE SIDE (WATERLINE)": 465.0,
	}
	for text in labels.keys():
		var label := Label.new()
		label.text = text
		label.position = Vector2(8, labels[text])
		label.add_theme_color_override("font_color", Color("5a8cb4"))
		add_child(label)


func _build_review_station() -> void:
	var glow := Sprite2D.new()
	glow.texture = load("res://assets/node_glow.png")
	glow.position = SAFETY_REVIEW_STATION
	glow.modulate = Color(0.9, 0.6, 0.25, 0.5)
	glow.scale = Vector2(0.75, 0.75)
	add_child(glow)
	review_glow = glow

	var label := Label.new()
	label.text = "SAFETY REVIEW (HITL)"
	label.add_theme_color_override("font_color", Color("ffb96b"))
	label.position = SAFETY_REVIEW_STATION + Vector2(-70, 26)
	label.size = Vector2(140, 20)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(label)


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

	var status := Label.new()
	status.text = "ws://localhost:8081"
	status.position = Vector2(16, 516)
	status.add_theme_color_override("font_color", Color("3a5a78"))
	add_child(status)


func _connect_socket() -> void:
	var err := socket.connect_to_url("ws://localhost:8081")
	if err != OK:
		push_warning("visualizer: could not start connection: %s" % err)


func _process(delta: float) -> void:
	socket.poll()
	var state := socket.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		connected = true
		while socket.get_available_packet_count() > 0:
			var packet := socket.get_packet().get_string_from_utf8()
			_handle_event(packet)
	elif state == WebSocketPeer.STATE_CLOSED:
		if connected:
			connected = false
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
		review_glow.modulate.a = 0.4 + 0.3 * abs(sin(review_pulse_t))


func _handle_event(raw: String) -> void:
	var parsed = JSON.parse_string(raw)
	if parsed == null or typeof(parsed) != TYPE_DICTIONARY:
		return

	var event_type: String = parsed.get("type", "")
	match event_type:
		"deconfliction_start":
			_clear_scene()
			var packages: Array = parsed.get("work_packages", [])
			for wp in packages:
				_spawn_marker(wp)
			_say("scanning %d work package(s) for spatial conflicts..." % packages.size())
		"deconfliction_result":
			var conflicts: Array = parsed.get("conflicts", [])
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
			review_pulsing = true
			if markers.has(wp_id):
				var m: Node2D = markers[wp_id]
				var line := Line2D.new()
				line.width = 2.0
				line.default_color = Color("ffb96b")
				line.points = PackedVector2Array([m.position, SAFETY_REVIEW_STATION])
				add_child(line)
				conflict_lines.append(line)
			_say("SAFETY REVIEW: %s awaiting human decision %s" % [wp_id, provenance])
		"approval_decided", "hitl_decided":
			review_pulsing = false
			if review_glow:
				review_glow.modulate.a = 0.5
			var decision: String = parsed.get("decision", parsed.get("approved", ""))
			_say("%s decision: %s" % [parsed.get("work_package_id", ""), decision])


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
		review_glow.modulate.a = 0.5


func _frame_to_x(frame) -> float:
	if frame == null:
		return (X_MIN + X_MAX) / 2.0
	var f: float = clamp(float(frame), FRAME_MIN, FRAME_MAX)
	return X_MIN + (f - FRAME_MIN) / (FRAME_MAX - FRAME_MIN) * (X_MAX - X_MIN)


func _band_y_for(wp: Dictionary) -> float:
	if wp.get("is_aloft", false):
		return BAND_ALOFT
	if wp.get("is_over_side", false):
		return BAND_OVER_SIDE
	var deck: String = str(wp.get("deck_level", "")).to_lower()
	if deck.find("2nd") != -1 or deck.find("second") != -1:
		return BAND_2ND_DECK
	if deck.find("3rd") != -1 or deck.find("third") != -1 or deck.find("hold") != -1:
		return BAND_3RD_DECK
	return BAND_MAIN_DECK


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

	# Frame-range bar showing the work package's spatial extent.
	var bar := Line2D.new()
	bar.width = 6.0
	bar.default_color = Color(color.r, color.g, color.b, 0.55)
	bar.points = PackedVector2Array([Vector2(x1 - node.position.x, 0), Vector2(x2 - node.position.x, 0)])
	node.add_child(bar)

	var glow := Sprite2D.new()
	glow.texture = load("res://assets/node_glow.png")
	glow.modulate = Color(color.r, color.g, color.b, 0.7)
	glow.scale = Vector2(0.4, 0.4)
	node.add_child(glow)

	var label := Label.new()
	label.text = id
	label.add_theme_color_override("font_color", color)
	label.position = Vector2(-40, -28)
	label.size = Vector2(80, 16)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	node.add_child(label)

	markers[id] = node
	marker_base_color[id] = color


func _flag_conflict(conflict: Dictionary, seen: Dictionary) -> void:
	var id: String = conflict.get("work_package_id", "")
	if markers.has(id):
		var sprite := markers[id].get_child(1) as Sprite2D  # glow is child index 1
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
