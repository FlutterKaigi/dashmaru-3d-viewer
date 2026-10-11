import 'package:dashmaru_3d_viewer/dashmaru_background.dart';
import 'package:dashmaru_3d_viewer/dashmaru_scene.dart';
import 'package:dashmaru_3d_viewer/main.dart';
import 'package:flutter_test/flutter_test.dart';

class _FailingScene extends DashmaruScene {
  @override
  Future<void> load({
    required DashmaruMotion initialMotion,
    DashmaruExpression initialExpression = DashmaruExpression.normal,
    DashmaruBackground initialBackground = DashmaruBackground.mint,
    double? initialTime,
    String? initialCamera,
    double? initialZoom,
  }) => Future<void>.error(
    StateError('model load regression fixture'),
    StackTrace.empty,
  );
}

void main() {
  test('malformed UTF-8 query values use the default view settings', () {
    for (final query in [
      'motion=%FF',
      'camera=%C0%AF',
      'expression=%ED%A0%80',
      'background=%E3%81',
      'motion=walk&unused=%FF',
    ]) {
      final uri = Uri.parse('https://example.test/?$query');
      expect(() => uri.queryParameters, throwsFormatException);

      final parameters = parseViewerQuery(uri);
      expect(parameters, isEmpty, reason: query);
      expect(DashmaruMotion.parse(parameters['motion']), DashmaruMotion.idle);
      expect(
        DashmaruExpression.parse(parameters['expression']),
        DashmaruExpression.normal,
      );
      expect(
        DashmaruBackground.parse(parameters['background']),
        DashmaruBackground.mint,
      );
    }
  });

  test('valid encoded query values are preserved', () {
    final uri = Uri.parse(
      'https://example.test/?motion=%77ave&time=0.75&expression=smile'
      '&background=night&camera=three%2Dquarter&zoom=2',
    );
    expect(parseViewerQuery(uri), {
      'motion': 'wave',
      'time': '0.75',
      'expression': 'smile',
      'background': 'night',
      'camera': 'three-quarter',
      'zoom': '2',
    });
  });

  testWidgets('model loading failures still show an error', (tester) async {
    await tester.pumpWidget(DashmaruApp(world: _FailingScene()));
    await tester.pump();

    expect(find.textContaining('3D モデルを読み込めませんでした。'), findsOneWidget);
    expect(
      find.textContaining('model load regression fixture'),
      findsOneWidget,
    );
    expect(find.text('だしゅまるを呼んでいます…'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
