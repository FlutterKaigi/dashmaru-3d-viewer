import 'package:flutter_scene/scene.dart' as scene;

import 'sitting_playback.dart';

/// Coordinates the real clips without requiring a renderer or GPU.
///
/// Seated exits retrace the grounded entrance before another clip fades in.
/// Blending a lowered pelvis directly with a gait would sink the feet.
class MotionPlayback<T> {
  MotionPlayback({
    required this.clips,
    required this.sitting,
    required this.sittingDuration,
    required this.motion,
    this.gaitEntrances = const {},
  });

  final Map<T, scene.AnimationClip> clips;
  final T sitting;
  final double sittingDuration;
  final Map<T, double> gaitEntrances;
  T motion;
  bool playing = true;
  double speed = 1;
  final Map<T, double> _transitionWeights = {};
  static const _transitionDuration = 0.3;
  double _transitionElapsed = 0;
  SittingExit? _sittingExit;
  bool _holdingEntrance = false;

  bool get leavingSeat => _sittingExit != null;

  /// The requested motion has not started while the character is rising.
  double get playbackTime => leavingSeat ? 0 : clips[motion]!.playbackTime;

  void selectMotion(T value, {bool animateTransition = true}) {
    if (!animateTransition) {
      _sittingExit = null;
      _startTransition(value, animateTransition: false);
      return;
    }
    if (value == motion) {
      setPlaying(true);
      return;
    }
    if (leavingSeat) {
      // A new destination does not restart standing up. Selecting Sit again
      // resumes the same authored pose forward, including midway through rising.
      motion = value;
      if (value == sitting) _sittingExit = null;
      setPlaying(true);
      return;
    }
    final seat = clips[sitting]!;
    if (motion == sitting && seat.weight == 1 && seat.playbackTime > 0) {
      _sittingExit = SittingExit(seat.playbackTime);
      _transitionWeights.clear();
      motion = value;
      setPlaying(true);
      return;
    }
    // During the initial entrance fade, retain every outgoing weight. The
    // first 0.3 seconds of Sit are standing, so this can fade normally.
    _startTransition(value);
  }

  void _startTransition(T value, {bool animateTransition = true}) {
    _holdingEntrance = false;
    _transitionWeights.clear();
    if (animateTransition) {
      for (final entry in clips.entries) {
        _transitionWeights[entry.key] = entry.value.weight;
      }
    }
    _transitionElapsed = 0;
    motion = value;
    final selected = clips[value]!;
    if (selected.weight == 0 || !animateTransition) selected.seek(0);
    for (final entry in clips.entries) {
      if (!animateTransition) entry.value.weight = entry.key == value ? 1 : 0;
      entry.value.playbackTimeScale = speed;
    }
    setPlaying(true);
  }

  void setPlaying(bool value) {
    playing = value;
    for (final entry in clips.entries) {
      entry.value.playing =
          value &&
          !_holdingEntrance &&
          (leavingSeat
              ? entry.key == sitting
              : entry.value.weight > 0 || entry.key == motion);
    }
  }

  void setSpeed(double value) {
    speed = value;
    for (final clip in clips.values) {
      clip.playbackTimeScale = value;
    }
  }

  void advance(double deltaSeconds) {
    if (!playing || deltaSeconds <= 0) return;
    final exit = _sittingExit;
    if (exit != null) {
      if (exit.advance(clips[sitting]!, deltaSeconds * speed)) {
        _sittingExit = null;
        // Neutral-start gestures meet this exact pose and can play directly.
        // Gaits first blend toward a fixed, grounded entrance phase.
        _startTransition(motion, animateTransition: false);
        final entrance = gaitEntrances[motion];
        if (entrance != null) {
          clips[motion]!
            ..seek(entrance)
            ..weight = 0;
          for (final key in clips.keys) {
            _transitionWeights[key] = 0;
          }
          _holdingEntrance = true;
          setPlaying(true);
        }
      }
      return;
    }
    if (_transitionWeights.isNotEmpty) {
      _transitionElapsed += deltaSeconds;
      final progress = (_transitionElapsed / _transitionDuration).clamp(
        0.0,
        1.0,
      );
      final eased = progress * progress * (3 - 2 * progress);
      for (final entry in clips.entries) {
        final start = _transitionWeights[entry.key]!;
        final target = entry.key == motion ? 1.0 : 0.0;
        entry.value.weight = start + (target - start) * eased;
        if (progress == 1 && entry.key != motion) entry.value.pause();
      }
      if (progress == 1) {
        _transitionWeights.clear();
        if (_holdingEntrance) {
          _holdingEntrance = false;
          setPlaying(true);
        }
      }
    }
    for (final entry in clips.entries) {
      if (entry.key == sitting) {
        SittingPlayback.advance(entry.value, deltaSeconds, sittingDuration);
      } else {
        entry.value.advance(deltaSeconds);
      }
    }
  }
}
