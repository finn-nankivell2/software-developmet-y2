from prelude import *
import fonts
from gameutil import surface_rounded_corners
from tooltip import Tooltip
from particles import DeflatingParticle

Onclick = Optional[Callable]


# Base class that all buttons inherit from
class AbstractButton(Sprite):
	def __init__(self, rect: FRect, onclick: Onclick = None):
		self.rect = rect
		self.onclick = onclick
		self.disabled = False

	# Set the function that will run when the button is clicked
	def set_onclick(self, onclick: Optional[Callable]):
		self.onclick = onclick
		return self

	def set_pos(self, pos: Vector2):
		self.rect.topleft = pos  # type: ignore
		return self

	# Is the button currently being hovered by the mouse
	def hovered(self) -> bool:
		return game.input.mouse_within(self.rect) and not self.disabled

	# Is the mouse hovering the button and pressed down
	def mouse_down_over(self, mbtn=0) -> bool:
		return self.hovered() and game.input.mouse_down(mbtn)

	# Is the button clicked on this frame only (subsequent frames of the mouse being pressed do not count)
	def clicked(self, mbtn=0) -> bool:
		return self.hovered() and game.input.mouse_pressed(mbtn)

	# Is the mouse clicked but not hovering the button
	def unclicked(self, mbtn=0) -> bool:
		return not self.hovered() and game.input.mouse_pressed(mbtn)

	# Check if clicked and run methods if so
	def update_move(self):
		if self.clicked() and self.onclick:
			self.onclick()
			game.audio.sounds.button.play()

	def update_draw(self):
		pygame.draw.rect(game.windowsystem.screen, palette.ERROR, self.rect)


# Button that renders a Surface
class SurfaceButton(AbstractButton):
	LAYER = "UI"

	def __init__(self, rect: FRect, texture: Surface, onclick: Onclick = None):
		super().__init__(rect, onclick)
		self._texture = texture

	@classmethod
	def from_surface(cls, surf: Surface):
		return cls(FRect(surf.get_rect()), surf)

	def update_draw(self):
		game.windowsystem.screen.blit(self._texture, self.rect)


# Button that has a text label
class NamedButton(AbstractButton):
	LAYER = "UI"
	CLICK_OFFSET = Vector2(-10, -10) # Button temporarily shrinks be this amount when clicked on

	def __init__(self, rect: FRect, text: str, colour: Color = palette.BLACK, onclick: Onclick = None):
		super().__init__(rect, onclick)
		self.c = colour
		self._text = text
		self._font = fonts.families.roboto.size(int(self.rect.height / 4))
		self._rendered = self._font.render(self._text, True, palette.TEXT)  # Render the text label

	# Draw the button background and render text on top
	def update_draw(self):
		rect = self.rect.copy()
		hovered = self.hovered()
		if self.mouse_down_over():
			rect.inflate_ip(-10, -10)
			hovered = False

		pygame.draw.rect(game.windowsystem.screen, self.c, rect, border_radius=5)
		pygame.draw.rect(game.windowsystem.screen, palette.GREY, rect.inflate(-10, -10), width=2, border_radius=5)

		if hovered:
			pygame.draw.rect(game.windowsystem.screen, palette.GREY, rect, width=2, border_radius=5)
		game.windowsystem.screen.blit(self._rendered, rect.center - Vector2(self._rendered.get_size()) / 2)


# Progress bar from 0 to 100 with a label
class ProgressBar(Sprite):
	LAYER = "UI"
	SIDE_PADDING = 10

	def __init__(self, rect: FRect, text: str, colour: Color = palette.BLACK):
		self.rect = rect
		self._text = text
		self.c = colour
		self.ratio = 0.0
		self._font = fonts.families.roboto.size(int(self.rect.height // 2))
		self._label = self._font.render(self._text, True, palette.TEXT)

		self._bar = Surface(self.rect.size, pygame.SRCALPHA)
		self.rerender()

	def with_tooltip(self, text: str):
		game.sprites.new(Tooltip(self._text, text, self.rect))
		return self

	# Set the percentage filled
	def set_ratio(self, ratio: float, rerender: bool = False):
		self.ratio = max(0.0, min(ratio, 1.0))
		if rerender:
			self.rerender()
		return self

	def rerender(self):
		self._bar.set_alpha(255)
		self._bar.fill(self.c)
		self._bar.blit( self._label, (ProgressBar.SIDE_PADDING, self._bar.get_height()/2 - self._label.get_height() / 2))

		bw = self._bar.get_width()

		rem = bw - (self._label.get_width() + ProgressBar.SIDE_PADDING*2)
		start = bw - rem
		end = bw - ProgressBar.SIDE_PADDING
		length = end - start

		barbg = FRect(start, ProgressBar.SIDE_PADDING, length, self.rect.height - ProgressBar.SIDE_PADDING*2)
		barfg = barbg.copy()
		barfg.width = barbg.width * self.ratio
		pygame.draw.rect(self._bar, palette.GREY, barbg)
		pygame.draw.rect(self._bar, palette.WHITE, barfg)

		self._bar = surface_rounded_corners(self._bar, 5)

	def update_draw(self):
		game.windowsystem.screen.blit(self._bar, self.rect.topleft)



# ProgressBar that watches a specific stat in the PlayerStateTrackingModule, and updates when that state updates
class TargettingProgressBar(ProgressBar):
	def __init__(self, *args, target=None, **kwargs):
		super().__init__(*args, **kwargs)
		self._target = target
		self._og_rect = self.rect.copy()

	def do_targeting(self):
		value = game.playerstate.get_property(self._target)
		if self.ratio != value:
			self.set_ratio(value)
			self.rerender()
			game.sprites.new(DeflatingParticle(self.rect.inflate(20, 20), palette.GREY, 60))

	def update_move(self):
		if self._target is not None:
			self.do_targeting()


# TargettingProgressBar that becomes transparent when a Playspace is under it
class DodgingProgressBar(TargettingProgressBar):
	def update_draw(self):
		if any(space.rect.colliderect(self.rect) for space in game.sprites.get("PLAYSPACE")):
			self._bar.set_alpha(100)
		else:
			self._bar.set_alpha(255)

		super().update_draw()


# UNUSED
class UserDebugLog(Sprite):
	LAYER = "UI"
	LOG_SHOW_LENGTH = 10

	def __init__(self, rect: FRect, num_lines: int = 9, text_size: int = 26, colour = palette.BLACK):
		self.rect = rect
		self.num_lines = num_lines
		self.text_size = text_size
		self._font = fonts.families.roboto.size(text_size)
		self._queue = []

		self.colour = colour
		self._tick = UserDebugLog.LOG_SHOW_LENGTH

	def display_to_queue(self, text):
		self._queue.append(text)

	def update_move(self):
		if len(self._queue) > self.num_lines:
			self._tick -= 1

		if self._tick < 1:
			self._tick = UserDebugLog.LOG_SHOW_LENGTH
			self._queue.pop(0)

	def update_draw(self):
		pygame.draw.rect(game.windowsystem.screen, self.colour, self.rect, border_radius=5)
		# pygame.draw.rect(game.windowsystem.screen, palette.GREY, self.rect.inflate(-5, -5), border_radius=5, width=2)

		rect = self.rect.copy()
		rect.inflate_ip(-20, -20)
		rect.height = self.text_size
		for text in itertools.islice(self._queue, self.num_lines):
			render = self._font.render(text, True, palette.TEXT)
			game.windowsystem.screen.blit(render, rect)
			rect.y += rect.height * 1.2


# Button that toggles another sprite on and off
class Dropdown(AbstractButton):
	LAYER = "FOREGROUND"

	def __init__(self, rect: FRect, elements: Sprite):
		super().__init__(rect, self.toggle)

		self.elements = elements
		self._dropped = False

	def toggle(self):
		self._dropped = not self._dropped

	def is_down(self) -> bool:
		return self._dropped

	def set_pos(self, pos: Vector2):
		self.rect.topleft = pos
		return self

	# If mouse clicks elsewhere, toggle off
	def unclicked(self, mbtn=0) -> bool:
		return not self.hovered() and (not self.elements.hovered() if self.elements else True) and game.input.mouse_pressed(mbtn)

	def update_move(self):
		super().update_move()

		if self._dropped and self.elements:
			self.elements.update_move()

		if self.elements:
			self.elements.set_pos(self.rect.topright + vec(10, 0))

		if self.unclicked():
			self._dropped = False

	def update_draw(self):
		pygame.draw.rect(game.windowsystem.screen, palette.BLACK, self.rect, border_radius=5)

		if self.hovered():
			pygame.draw.rect(game.windowsystem.screen, palette.GREY, self.rect, width=2, border_radius=5)
		else:
			pygame.draw.rect(game.windowsystem.screen, palette.GREY, self.rect.inflate(-5, -5), width=2, border_radius=5)

		# Draw arrow
		tr = vec(self.rect.size) * 0.4
		if self._dropped:
			triangle = [self.rect.midbottom + vec(tr.x/2, -tr.y), self.rect.midtop + vec(tr.x/2, tr.y), self.rect.midleft + vec(tr.x, 0)]
		else:
			triangle = [self.rect.midbottom - vec(tr.x/2, tr.y), self.rect.midtop - vec(tr.x/2, -tr.y), self.rect.midright - vec(tr.x, 0)]

		pygame.draw.polygon(game.windowsystem.screen, palette.WHITE, triangle)

		if self._dropped and self.elements:
			self.elements.update_draw()
