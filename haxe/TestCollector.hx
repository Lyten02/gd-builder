package;

#if macro
import haxe.macro.Context;
import haxe.macro.Expr;
#end

class TestCollector {
	public static macro function addAllCases(runner:Expr):Expr {
		var roots = getScanRoots();
		var classes = new Array<{pack:Array<String>, name:String}>();
		for (root in roots) scan(root, [], classes);
		classes.sort((a, b) -> {
			var ap = a.pack.join(".") + "." + a.name;
			var bp = b.pack.join(".") + "." + b.name;
			return ap < bp ? -1 : ap > bp ? 1 : 0;
		});
		var calls = new Array<Expr>();
		for (c in classes) {
			var tp:TypePath = { pack: c.pack, name: c.name, params: [] };
			calls.push(macro $runner.addCase(new $tp()));
		}
		return macro $b{calls};
	}

	#if macro
	static function getScanRoots():Array<String> {
		var onlyModule = Context.definedValue("module_test");
		if (onlyModule != null && onlyModule != "1") {
			var p = "modules/" + onlyModule + "/test";
			return sys.FileSystem.exists(p) ? [p] : [];
		}
		var projectOnly = Context.definedValue("project_only_test");
		var paths = new Array<String>();
		if (sys.FileSystem.exists("test")) paths.push("test");
		if (projectOnly != null) return paths;
		if (sys.FileSystem.exists("modules")) {
			for (mod in sys.FileSystem.readDirectory("modules")) {
				var p = "modules/" + mod + "/test";
				if (sys.FileSystem.exists(p) && sys.FileSystem.isDirectory(p)) paths.push(p);
			}
		}
		return paths;
	}

	static function scan(root:String, pack:Array<String>, out:Array<{pack:Array<String>, name:String}>) {
		var dirPath = pack.length == 0 ? root : root + "/" + pack.join("/");
		if (!sys.FileSystem.exists(dirPath)) return;
		for (item in sys.FileSystem.readDirectory(dirPath)) {
			var full = dirPath + "/" + item;
			if (sys.FileSystem.isDirectory(full)) {
				scan(root, pack.concat([item]), out);
			} else if (StringTools.endsWith(item, ".hx")) {
				var name = item.substr(0, item.length - 3);
				if (name == "TestMain" || name == "TestCollector") continue;
				if (!isTestCase(name, full)) continue;
				out.push({ pack: pack.copy(), name: name });
			}
		}
	}

	static var EXTENDS_TEST = ~/class\s+\w+\s+extends\s+(utest\.)?Test\b/;

	static function isTestCase(className:String, path:String):Bool {
		var starts = StringTools.startsWith(className, "Test");
		var ends = StringTools.endsWith(className, "Spec");
		if (!starts && !ends) return false;
		if (StringTools.endsWith(className, "Fixture")) return false;
		return try EXTENDS_TEST.match(sys.io.File.getContent(path)) catch (_) false;
	}
	#end
}
