//go:build !windows

package main

import (
	"fmt"
	"os"
)

func avisar(titulo, texto string) {
	fmt.Fprintln(os.Stderr, titulo+": "+texto)
}
