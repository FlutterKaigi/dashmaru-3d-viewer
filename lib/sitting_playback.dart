import 'package:flutter_scene/scene.dart' as scene;

/// The Sit clip enters once, then repeats its authored seated section.
/// Its pose at 2.4 seconds matches the final pose, so the repeat stays seated.
abstract final class SittingPlayback {
  static const loopStart = 2.4;

  static double position(double time, double duration) {
    if (!time.isFinite || duration <= loopStart) return 0;
    if (time <= duration) return time.clamp(0, duration);
    return loopStart + (time - loopStart) % (duration - loopStart);
  }

  /// Advance the actual bound clip, retaining its pause and speed settings.
  static void advance(
    scene.AnimationClip clip,
    double deltaSeconds,
    double duration,
  ) {
    if (!clip.playing || deltaSeconds <= 0) return;
    clip.seek(
      position(
        clip.playbackTime + deltaSeconds * clip.playbackTimeScale,
        duration,
      ),
    );
  }
}

/// Reuses the grounded Sit entrance in reverse instead of blending leg bends.
class SittingExit {
  SittingExit(double initialTime)
    : _holdTime = initialTime > SittingPlayback.loopStart ? initialTime : null,
      _riseStart = initialTime.clamp(0, SittingPlayback.loopStart);

  static const _settleDuration = 0.18;
  static const _riseDuration = 1.0;
  final double? _holdTime;
  final double _riseStart;
  double _elapsed = 0;

  /// Returns true only after the clip has reached its standing pose.
  bool advance(scene.AnimationClip clip, double scaledDeltaSeconds) {
    if (!clip.playing || scaledDeltaSeconds <= 0) return false;
    _elapsed += scaledDeltaSeconds;
    final holdTime = _holdTime;
    final settle = holdTime == null ? 0.0 : _settleDuration;
    if (holdTime != null && _elapsed < settle) {
      final progress = _smooth(_elapsed / settle);
      clip.seek(holdTime + (SittingPlayback.loopStart - holdTime) * progress);
      return false;
    }
    final duration = _riseDuration * _riseStart / SittingPlayback.loopStart;
    final progress = duration == 0
        ? 1.0
        : ((_elapsed - settle) / duration).clamp(0.0, 1.0);
    clip.seek(_riseStart * (1 - _smooth(progress)));
    return progress == 1;
  }

  static double _smooth(double progress) =>
      progress * progress * (3 - 2 * progress);
}
