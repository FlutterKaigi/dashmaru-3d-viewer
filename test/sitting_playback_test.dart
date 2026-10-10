import 'package:flutter_scene/scene.dart' as scene;
import 'package:flutter_test/flutter_test.dart';
import 'package:dashmaru_3d_viewer/sitting_playback.dart';

const _duration = 6.4;

class _SittingTimeline extends scene.Animation {
  @override
  double get endTime => _duration;
}

scene.AnimationClip _clip() =>
    scene.Node(name: 'Hips').createAnimationClip(_SittingTimeline())..play();

void main() {
  test('sitting down plays once before the seated section repeats', () {
    final clip = _clip();
    SittingPlayback.advance(clip, 1.2, _duration);
    expect(clip.playbackTime, closeTo(1.2, 1e-6));
    SittingPlayback.advance(clip, 5.3, _duration);
    expect(clip.playbackTime, closeTo(2.5, 1e-6));

    for (var frame = 0; frame < 3600; frame++) {
      SittingPlayback.advance(clip, 0.05, _duration);
      expect(clip.playbackTime, inInclusiveRange(2.4, 6.4));
      expect(clip.playing, isTrue);
    }
  });

  test('pause and speed changes keep the seat loop continuous', () {
    final clip = _clip()
      ..seek(6.3)
      ..pause();
    SittingPlayback.advance(clip, 20, _duration);
    expect(clip.playbackTime, 6.3);
    clip
      ..playbackTimeScale = 0.5
      ..play();
    SittingPlayback.advance(clip, 0.4, _duration);
    expect(clip.playbackTime, closeTo(2.5, 1e-6));
    clip.playbackTimeScale = 1.5;
    SittingPlayback.advance(clip, 3, _duration);
    expect(clip.playbackTime, closeTo(3.0, 1e-6));
  });

  test('long URL seeks stay seated and preserve their remainder', () {
    expect(SittingPlayback.position(0, _duration), 0);
    expect(SittingPlayback.position(1.2, _duration), 1.2);
    expect(SittingPlayback.position(6.4, _duration), 6.4);
    expect(SittingPlayback.position(10.5, _duration), closeTo(2.5, 1e-6));
    expect(SittingPlayback.position(120, _duration), closeTo(4.0, 1e-6));
    expect(SittingPlayback.position(-1, _duration), 0);
    expect(SittingPlayback.position(double.nan, _duration), 0);
  });

  test(
    'outgoing paused clips stay still and reentry can replay the entrance',
    () {
      final clip = _clip()..seek(3.2);
      clip.pause();
      SittingPlayback.advance(clip, 1, _duration);
      expect(clip.playbackTime, 3.2);
      clip.replay();
      SittingPlayback.advance(clip, 0.1, _duration);
      expect(clip.playbackTime, closeTo(0.1, 1e-6));
    },
  );
}
