// Use the right jQuery source on the test page (and iframes)
(function() {
	/* global loadTests: false */

	var src,
		path = window.location.pathname.split( "test" )[ 0 ],
		QUnit = window.QUnit || parent.QUnit,
		require = window.require || parent.require;

	// iFrames won't load AMD (the iframe tests synchronously expect jQuery to be there)
	QUnit.config.urlConfig.push({
		id: "amd",
		label: "Load with AMD",
		tooltip: "Load the AMD jQuery file (and its dependencies)"
	});
	// If QUnit is on window, this is the main window
	// This detection allows AMD tests to be run in an iframe
	if ( QUnit.urlParams.amd && window.QUnit ) {
		require.config({
			baseUrl: path,
			paths: {
				sizzle: "external/sizzle/dist/sizzle"
			}
		});
		src = "src/jquery";
		// Include tests if specified
		if ( typeof loadTests !== "undefined" ) {
			require( [ src ], loadTests );
		} else {
			require( [ src ] );
		}
		return;
	}

	// Config parameter to use minified jQuery
	QUnit.config.urlConfig.push({
		id: "dev",
		label: "Load unminified",
		tooltip: "Load the development (unminified) jQuery file"
	});
	if ( QUnit.urlParams.dev ) {
		src = "dist/jquery.js";
	} else {
		src = "dist/jquery.min.js";
	}

	// Load jQuery
	var script = document.createElement("script");
	script.id = "jquery-js";
	script.src = path + src;
	script.async = false;
	script.defer = false;
	document.getElementsByTagName("head")[0].appendChild(script);
	//document.write( "<script id='jquery-js' src='" + path + src + "'><\x2Fscript>" );

	// Synchronous-only tests
	// Other tests are loaded from the test page
	if ( typeof loadTests !== "undefined" ) {
		var ready_script = document.createElement("script");
		ready_script.src = path + "test/unit/ready.js";
		ready_script.async = false;
		ready_script.defer = false;
		document.getElementsByTagName("head")[0].appendChild(ready_script);
		//document.write( "<script src='" + path + "test/unit/ready.js'><\x2Fscript>");
	}

})();
