package turbotides

import com.williamcallahan.tui4j.compat.bubbletea.Program
import java.nio.file.Path
import kotlin.system.exitProcess

fun main(args: Array<String>) {
    val version = java.util.Properties().apply {
        MainVersion::class.java.getResourceAsStream("/version.properties").use { load(it) }
    }.getProperty("version")
    val xdgData = System.getenv("XDG_DATA_HOME")?.takeIf { it.isNotBlank() && Path.of(it).isAbsolute }
    var data = Path.of(xdgData ?: "${System.getProperty("user.home")}/.local/share", "turbotides-tui")
    var telemetry: Path? = null
    var index = 0
    while (index < args.size) {
        when (val arg = args[index++]) {
            "--help", "-h" -> {
                println(
                    """
                    Turbo Tides TUI $version — six circuits, three laps, one terminal.
                    Usage: turbotides-tui [--data-dir DIR] [--telemetry FILE]
                    --data-dir DIR    Isolate local settings and personal bests.
                    --telemetry FILE  Write opt-in local diagnostics; never changes race rules.
                    --version        Show version.
                    Play in a UTF-8 color terminal, at least 64 columns × 24 rows.
                    W/Up throttle, S/Down brake; A/D or arrows steer (repeat to hold).
                    Space drift mode, B nitro mode, C rear view. Esc pause, ? help, Q quit.
                    """.trimIndent(),
                )
                return
            }
            "--version" -> {
                println("Turbo Tides TUI $version")
                return
            }
            "--data-dir", "--telemetry" -> {
                val value = args.getOrNull(index++)
                if (value == null || value.startsWith("--")) {
                    System.err.println("$arg requires a path")
                    exitProcess(2)
                }
                if (arg == "--data-dir") data = Path.of(value) else telemetry = Path.of(value)
            }
            else -> {
                System.err.println("Unknown option: $arg. Use --help.")
                exitProcess(2)
            }
        }
    }
    if (System.console()?.isTerminal != true) {
        System.err.println("Open a terminal to play Turbo Tides TUI. Use --help for options.")
        exitProcess(2)
    }
    val game = TerminalGame(Records(data), telemetry)
    try {
        Program(game).withAltScreen().withReportFocus().run()
    } finally {
        game.close()
    }
}

private object MainVersion
