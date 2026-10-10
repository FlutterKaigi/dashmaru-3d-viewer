import 'package:flutter_scene/scene.dart' as scene;
import 'package:flutter_test/flutter_test.dart';
import 'package:dashmaru_3d_viewer/dashmaru_scene.dart';

const _jumpDuration = 2.4;

DashmaruExpression _face(
  double time, {
  DashmaruMotion motion = DashmaruMotion.jump,
  DashmaruExpression preferred = DashmaruExpression.smile,
}) => DashmaruExpression.forPlayback(
  motion: motion,
  preferred: preferred,
  playbackTime: time,
  duration: _jumpDuration,
);

class _JumpTimeline extends scene.Animation {
  @override
  double get endTime => _jumpDuration;
}

scene.AnimationClip _jumpClip() {
  // The real Flutter Scene playback clock needs a bound node and duration,
  // but no rendered Scene / GPU. This catches pause, speed and loop behavior
  // without substituting a separate simulated expression clock.
  final target = scene.Node(name: 'Hips');
  return target.createAnimationClip(_JumpTimeline())..loop = true;
}

void main() {
  test('four distinct choices include strain and retire the deadpan URL', () {
    expect(DashmaruExpression.values, [
      DashmaruExpression.normal,
      DashmaruExpression.smile,
      DashmaruExpression.spiral,
      DashmaruExpression.strain,
    ]);
    expect(DashmaruExpression.parse('strain'), DashmaruExpression.strain);
    expect(DashmaruExpression.parse('deadpan'), DashmaruExpression.normal);
  });

  test(
    'jump uses strain only between takeoff and landing for every preference',
    () {
      for (final preferred in DashmaruExpression.values) {
        for (final time in [0.0, _jumpDuration * 0.23 - 0.00001]) {
          expect(_face(time, preferred: preferred), DashmaruExpression.normal);
        }
        for (final time in [
          _jumpDuration * 0.23,
          1.2,
          _jumpDuration * 0.81 - 0.00001,
        ]) {
          expect(_face(time, preferred: preferred), DashmaruExpression.strain);
        }
        for (final time in [_jumpDuration * 0.81, 2.2, _jumpDuration]) {
          expect(_face(time, preferred: preferred), DashmaruExpression.normal);
        }
      }
    },
  );

  test('a seek resolves the paused face and resume follows playback speed', () {
    final clip = _jumpClip()..seek(1.2);
    expect(_face(clip.playbackTime), DashmaruExpression.strain);
    clip.advance(10);
    expect(clip.playbackTime, 1.2);
    expect(_face(clip.playbackTime), DashmaruExpression.strain);

    clip
      ..playbackTimeScale = 1.5
      ..play()
      ..advance(0.5);
    expect(_face(clip.playbackTime), DashmaruExpression.normal);

    clip
      ..seek(0.5)
      ..playbackTimeScale = 0.5
      ..advance(0.1);
    expect(_face(clip.playbackTime), DashmaruExpression.normal);
    clip.advance(0.1);
    expect(_face(clip.playbackTime), DashmaruExpression.strain);
  });

  test('looping returns to normal before the next airborne phase', () {
    final clip = _jumpClip()
      ..seek(2.39)
      ..play();
    clip.advance(0.03);
    expect(clip.playbackTime, closeTo(0.02, 0.000001));
    expect(_face(clip.playbackTime), DashmaruExpression.normal);
    clip.advance(0.55);
    expect(_face(clip.playbackTime), DashmaruExpression.strain);
  });

  test(
    'switching away immediately restores any manually selected expression',
    () {
      for (final preferred in DashmaruExpression.values) {
        for (final motion in DashmaruMotion.values) {
          if (motion == DashmaruMotion.jump) continue;
          // The outgoing Jump can still be airborne during a rapid crossfade.
          expect(_face(1.2, preferred: preferred), DashmaruExpression.strain);
          expect(_face(1.2, motion: motion, preferred: preferred), preferred);
        }
      }
    },
  );
}
