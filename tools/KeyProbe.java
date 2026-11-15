import com.williamcallahan.tui4j.compat.bubbletea.*;
import java.nio.file.*;
public final class KeyProbe implements Model {
    private final Path output;
    KeyProbe(Path output) { this.output=output; }
    public Command init() { return null; }
    public String view() { return "Keyboard probe ready"; }
    public UpdateResult<KeyProbe> update(Message message) {
        if(message instanceof KeyPressMessage key) {
            try { Files.writeString(output, System.nanoTime()+" "+key.key()+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND); }
            catch(Exception error) { throw new IllegalStateException(error); }
            if(key.key().equals("q")) return new UpdateResult<>(this,Command.quit());
        }
        return new UpdateResult<>(this,null);
    }
    public static void main(String[] args) { new Program(new KeyProbe(Path.of(args[0]))).withAltScreen().run(); }
}
