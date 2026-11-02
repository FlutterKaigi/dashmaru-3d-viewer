import 'dart:convert';
import 'dart:js_interop';
import 'dart:ui' as ui;

import 'package:dashmaru_3d_viewer/dashmaru_background.dart';
import 'package:dashmaru_3d_viewer/dashmaru_scene.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_scene/scene.dart' as scene;

const _canvas = Color(0xFFF8F9F3);
const _ink = Color(0xFF183E36);
const _green = Color(0xFF287757);
const _muted = Color(0xFF698179);

@JS('document')
external _Document get _document;

extension type _Document(JSObject _) implements JSObject {
  external _Body get body;
  external _Anchor createElement(String tagName);
}

extension type _Body(JSObject _) implements JSObject {
  external void appendChild(_Anchor child);
}

extension type _Anchor(JSObject _) implements JSObject {
  external set href(String value);
  external set download(String value);
  external set textContent(String value);
  external void setAttribute(String name, String value);
  external void click();
  external void remove();
}

/// A browser-only preview that exports web/ogp.png at exactly 1200 × 630.
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Keep the export control available to browser accessibility tools.
  WidgetsBinding.instance.ensureSemantics();
  runApp(const OgpPreviewApp());
}

class OgpPreviewApp extends StatelessWidget {
  const OgpPreviewApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'だしゅまる 3D — OGP Preview',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      fontFamily: 'sans-serif',
      scaffoldBackgroundColor: _canvas,
      colorScheme: ColorScheme.fromSeed(seedColor: _green),
    ),
    home: const _OgpPreview(),
  );
}

class _OgpPreview extends StatefulWidget {
  const _OgpPreview();

  @override
  State<_OgpPreview> createState() => _OgpPreviewState();
}

class _OgpPreviewState extends State<_OgpPreview> {
  final _artboardKey = GlobalKey();
  _Anchor? _downloadLink;
  bool _ready = false;
  bool _downloading = false;

  @override
  void dispose() {
    _downloadLink?.remove();
    super.dispose();
  }

  Future<void> _savePng() async {
    setState(() => _downloading = true);
    ui.Image? image;
    try {
      await WidgetsBinding.instance.endOfFrame;
      final boundary =
          _artboardKey.currentContext!.findRenderObject()!
              as RenderRepaintBoundary;
      image = await boundary.toImage(pixelRatio: 1);
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      if (data == null) throw StateError('PNG の生成に失敗しました。');
      final bytes = data.buffer.asUint8List(
        data.offsetInBytes,
        data.lengthInBytes,
      );
      final anchor = _document.createElement('a')
        ..href = 'data:image/png;base64,${base64Encode(bytes)}'
        ..download = 'ogp.png'
        ..textContent = '生成した PNG をダウンロード'
        ..setAttribute('id', 'ogp-download')
        ..setAttribute(
          'style',
          'position:fixed;left:12px;bottom:76px;z-index:2147483647;'
              'padding:12px 16px;border:1px solid #287757;border-radius:8px;'
              'background:#f8f9f3;color:#287757;font:14px sans-serif;'
              'max-width:calc(100vw - 24px);box-sizing:border-box;',
        );
      _downloadLink?.remove();
      _downloadLink = anchor;
      _document.body.appendChild(anchor);
      anchor.click();
    } catch (error, stack) {
      debugPrint('OGP preview capture failed: $error\n$stack');
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('PNG を保存できませんでした。\n$error')));
      }
    } finally {
      image?.dispose();
      if (mounted) setState(() => _downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Column(
      children: [
        Expanded(
          child: Center(
            child: FittedBox(
              child: RepaintBoundary(
                key: _artboardKey,
                child: SizedBox(
                  width: 1200,
                  height: 630,
                  child: _OgpPoster(
                    onReady: () => setState(() => _ready = true),
                  ),
                ),
              ),
            ),
          ),
        ),
        SafeArea(
          top: false,
          minimum: const EdgeInsets.fromLTRB(12, 8, 12, 12),
          child: Wrap(
            alignment: WrapAlignment.center,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 12,
            runSpacing: 4,
            children: [
              const Text('1200 × 630 PNG', style: TextStyle(fontSize: 13)),
              FilledButton.icon(
                onPressed: _ready && !_downloading ? _savePng : null,
                icon: const Icon(Icons.download_rounded, size: 18),
                label: Text(_downloading ? 'PNG を生成中…' : 'PNG を保存'),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _OgpPoster extends StatefulWidget {
  const _OgpPoster({required this.onReady});

  final VoidCallback onReady;

  @override
  State<_OgpPoster> createState() => _OgpPosterState();
}

class _OgpPosterState extends State<_OgpPoster> {
  final _world = DashmaruScene(cameraTargetY: 1.5);
  bool _ready = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      await _world.load(
        initialMotion: DashmaruMotion.wave,
        initialExpression: DashmaruExpression.smile,
        initialBackground: DashmaruBackground.mint,
        initialTime: 1.2,
        initialCamera: 'three-quarter',
        initialZoom: 1.1,
      );
      _world.setPlaying(false);
      _world.tick(Duration.zero, 0);
      if (mounted) {
        setState(() => _ready = true);
        widget.onReady();
      }
    } catch (error, stack) {
      debugPrint('OGP preview model loading failed: $error\n$stack');
      if (mounted) setState(() => _error = error);
    }
  }

  @override
  Widget build(BuildContext context) => MediaQuery.withNoTextScaling(
    child: ColoredBox(
      color: _canvas,
      child: Stack(
        children: [
          Positioned(
            left: 650,
            top: 52,
            width: 500,
            height: 500,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: DashmaruBackground.mint.gradient,
                border: Border.all(color: const Color(0xFFDCE8D8)),
              ),
            ),
          ),
          Positioned(
            left: 610,
            top: 26,
            width: 580,
            height: 550,
            child: _model(),
          ),
          const Positioned(
            left: 72,
            top: 67,
            child: Text(
              'FLUTTERKAIGI  /  DASHMARU 3D',
              style: TextStyle(
                color: _green,
                fontSize: 13,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.8,
              ),
            ),
          ),
          const Positioned(
            left: 68,
            top: 129,
            width: 560,
            child: Text(
              'だしゅまる、\n3Dになる。',
              style: TextStyle(
                color: _ink,
                fontSize: 68,
                fontWeight: FontWeight.w800,
                height: 1.24,
                letterSpacing: -2.2,
              ),
            ),
          ),
          const Positioned(
            left: 73,
            top: 335,
            child: Text(
              'ブラウザーで、動く。眺める。',
              style: TextStyle(
                color: _ink,
                fontSize: 23,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.3,
              ),
            ),
          ),
          const Positioned(
            left: 74,
            top: 392,
            child: Text(
              '13の動き  ·  4つの表情  ·  4つの背景',
              style: TextStyle(
                color: _muted,
                fontSize: 16,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.3,
              ),
            ),
          ),
          const Positioned(
            left: 74,
            top: 463,
            width: 44,
            height: 3,
            child: ColoredBox(color: _green),
          ),
          const Positioned(
            left: 74,
            top: 488,
            child: Text(
              'dashmaru.flutterkaigi.jp',
              style: TextStyle(
                color: _green,
                fontSize: 20,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.4,
              ),
            ),
          ),
          const Positioned(
            right: 55,
            bottom: 34,
            child: Text(
              '© 2026 FlutterKaigi',
              style: TextStyle(
                color: _muted,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    ),
  );

  Widget _model() {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(48),
          child: Text(
            '3Dモデルを読み込めませんでした。\n$_error',
            textAlign: TextAlign.center,
            maxLines: 6,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: _ink, fontSize: 18),
          ),
        ),
      );
    }
    if (!_ready) {
      return const Center(
        child: CircularProgressIndicator(color: _green, strokeWidth: 2),
      );
    }
    return scene.SceneView(
      _world.sceneGraph,
      cameraBuilder: _world.camera,
      onTick: _world.tick,
    );
  }
}
