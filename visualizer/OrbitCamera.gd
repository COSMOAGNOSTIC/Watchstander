extends Node3D
## Minimal mouse-drag orbit camera for the 3D blockout demo view
## (Main3D.tscn). No dependencies, no networking -- this is purely a
## "look at the pretty picture" control, unrelated to the live 2D
## visualizer's WebSocket-driven Main.gd.
##
## Left-drag to orbit, scroll wheel to zoom.

@export var distance := 45.0
@export var min_distance := 15.0
@export var max_distance := 150.0
@export var rotate_speed := 0.01

var _yaw := 0.55
var _pitch := -0.3
var _dragging := false

@onready var camera: Camera3D = $Camera3D


func _ready() -> void:
	_update_camera()


func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			_dragging = event.pressed
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = clamp(distance - 5.0, min_distance, max_distance)
			_update_camera()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = clamp(distance + 5.0, min_distance, max_distance)
			_update_camera()
	elif event is InputEventMouseMotion and _dragging:
		_yaw -= event.relative.x * rotate_speed
		_pitch = clamp(_pitch - event.relative.y * rotate_speed, -1.3, -0.05)
		_update_camera()


func _update_camera() -> void:
	var offset := Vector3(
		distance * cos(_pitch) * sin(_yaw),
		distance * sin(-_pitch),
		distance * cos(_pitch) * cos(_yaw)
	)
	camera.position = offset
	camera.look_at(Vector3.ZERO, Vector3.UP)
