import 'package:flutter_scene/scene.dart' as scene;
import 'package:flutter_test/flutter_test.dart';
import 'package:dashmaru_3d_viewer/motion_playback.dart';

enum _Motion { sit, idle, walk, run, jump }

class _Timeline extends scene.Animation {
  _Timeline(this.duration);
  final double duration;
  @override
  double get endTime => duration;
}

MotionPlayback<_Motion> _player() {
  final target = scene.Node(name: 'Hips');
  final clips = {
    for (final motion in _Motion.values)
      motion:
          target.createAnimationClip(
              _Timeline(motion == _Motion.sit ? 6.4 : 10),
            )
            ..weight = 0
            ..loop = motion != _Motion.sit,
  };
  return MotionPlayback(
    clips: clips,
    sitting: _Motion.sit,
    sittingDuration: 6.4,
    motion: _Motion.idle,
    gaitEntrances: const {_Motion.walk: 0.5775, _Motion.run: 0.057},
  )..selectMotion(_Motion.sit, animateTransition: false);
}

void _step(MotionPlayback<_Motion> player, double seconds) {
  for (var i = 0; i < (seconds * 100).round(); i++) {
    player.advance(0.01);
  }
}

void main() {
  test('a seated exit reaches standing before the requested gesture plays', () {
    final player = _player();
    final sit = player.clips[_Motion.sit]!;
    final jump = player.clips[_Motion.jump]!;
    sit.seek(4.1);
    jump.seek(1.2);
    player.selectMotion(_Motion.jump);
    expect(player.motion, _Motion.jump);
    expect(player.leavingSeat, isTrue);
    _step(player, 0.7);
    expect(sit.playbackTime, lessThan(2.4));
    expect(sit.weight, 1);
    expect(jump.weight, 0);
    expect(jump.playbackTime, 1.2);
    expect(player.playbackTime, 0);
    _step(player, 0.5);
    expect(player.leavingSeat, isFalse);
    expect(sit.weight, 0);
    expect(sit.playbackTime, 0);
    expect(jump.weight, 1);
    expect(jump.playbackTime, greaterThan(0));
  });

  test('pause and speed apply while standing up', () {
    final player = _player();
    final sit = player.clips[_Motion.sit]!..seek(4.1);
    player.selectMotion(_Motion.idle);
    _step(player, 0.1);
    player.setPlaying(false);
    final frozen = sit.playbackTime;
    _step(player, 2);
    expect(sit.playbackTime, frozen);
    expect(player.leavingSeat, isTrue);
    player.setSpeed(0.5);
    player.setPlaying(true);
    _step(player, 1);
    expect(player.leavingSeat, isTrue);
    player.setSpeed(1.5);
    _step(player, 0.4);
    expect(player.leavingSeat, isFalse);
    expect(player.clips[_Motion.idle]!.weight, 1);
  });

  test('rapid choices update the destination without restarting the exit', () {
    final player = _player();
    final sit = player.clips[_Motion.sit]!..seek(3.2);
    player.selectMotion(_Motion.walk);
    _step(player, 0.6);
    final halfway = sit.playbackTime;
    player.selectMotion(_Motion.run);
    player.selectMotion(_Motion.jump);
    expect(sit.playbackTime, halfway);
    expect(player.clips[_Motion.run]!.weight, 0);
    _step(player, 0.6);
    expect(player.leavingSeat, isFalse);
    expect(player.clips[_Motion.jump]!.weight, 1);
    expect(player.clips[_Motion.walk]!.weight, 0);
  });

  test('choosing Sit during the rise reverses smoothly back into sitting', () {
    final player = _player();
    final sit = player.clips[_Motion.sit]!..seek(4.1);
    player.selectMotion(_Motion.run);
    _step(player, 0.6);
    final halfway = sit.playbackTime;
    expect(halfway, inExclusiveRange(0, 2.4));
    player.selectMotion(_Motion.sit);
    expect(player.leavingSeat, isFalse);
    expect(sit.playbackTime, halfway);
    expect(sit.weight, 1);
    _step(player, 4);
    expect(sit.playbackTime, inInclusiveRange(2.4, 6.4));
    expect(player.clips[_Motion.run]!.weight, 0);
  });

  test('interrupting the initial Sit fade preserves all current weights', () {
    final player = _player()
      ..selectMotion(_Motion.walk, animateTransition: false)
      ..selectMotion(_Motion.sit);
    _step(player, 0.1);
    final weights = player.clips.map((key, clip) => MapEntry(key, clip.weight));
    player.selectMotion(_Motion.run);
    expect(player.leavingSeat, isFalse);
    for (final entry in weights.entries) {
      expect(player.clips[entry.key]!.weight, entry.value);
    }
    _step(player, 0.4);
    expect(player.clips[_Motion.run]!.weight, 1);
    expect(player.clips[_Motion.sit]!.weight, 0);
  });

  test('gait entrance fades from standing before its clock advances', () {
    final player = _player();
    final sit = player.clips[_Motion.sit]!..seek(4.1);
    final run = player.clips[_Motion.run]!;
    player.selectMotion(_Motion.run);
    _step(player, 1.18);
    expect(player.leavingSeat, isFalse);
    expect(sit.playbackTime, 0);
    expect(sit.weight, 0);
    expect(run.weight, 0);
    expect(run.playbackTime, 0.057);
    _step(player, 0.15);
    expect(run.weight, closeTo(0.5, 1e-6));
    expect(run.playbackTime, 0.057);
    player.setPlaying(false);
    _step(player, 0.5);
    expect(run.weight, closeTo(0.5, 1e-6));
    player.setPlaying(true);
    _step(player, 0.2);
    expect(run.weight, 1);
    expect(run.playbackTime, greaterThan(0.057));
  });

  test('reset cancels the exit immediately', () {
    final player = _player();
    player.clips[_Motion.sit]!.seek(4.1);
    player.selectMotion(_Motion.run);
    _step(player, 0.4);
    player.selectMotion(_Motion.idle, animateTransition: false);
    expect(player.leavingSeat, isFalse);
    expect(player.clips[_Motion.idle]!.weight, 1);
    expect(player.clips[_Motion.sit]!.weight, 0);
    _step(player, 2);
    expect(player.motion, _Motion.idle);
  });
}
