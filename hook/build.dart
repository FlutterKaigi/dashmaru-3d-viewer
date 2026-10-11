import 'dart:io';

import 'package:flutter_scene/build_hooks.dart';
import 'package:hooks/hooks.dart';

void main(List<String> args) async {
  await build(args, (input, output) async {
    final model = File.fromUri(
      input.packageRoot.resolve('assets/models/dashmaru.glb'),
    );
    if (!model.existsSync()) {
      throw StateError(
        'assets/models/dashmaru.glb is missing. Clone the complete repository '
        'or run python3 tool/build_dashmaru.py from the repository root.',
      );
    }
    // Convert the distributed model assets for Flutter Scene.
    buildScenes(
      buildInput: input,
      buildOutput: output,
      discoveryRoot: 'assets/models/',
    );
  });
}
