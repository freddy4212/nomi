#!/bin/sh

# Navigate to the base directory of the repo
cd "${0%/*}/.."

c2dot() {
    local src=src/$1.c
    local dst=docs/dot/$1.dot

    echo "Generating $dst"

    awk -F "[(), ]+" '
        BEGIN {
            print "digraph mpix_op_convert_list {"
            print "    node [fontname=monospace, fontsize=10, shape=record];"
        }

        function conversion(fmt1, fmt2, label) {
            print ""
	        print "    "fmt1" [ label=\""fmt1"\" URL=\"@ref MPIX_FMT_"fmt1"\"];"
	        print "    "fmt2" [ label=\""fmt2"\" URL=\"@ref MPIX_FMT_"fmt2"\"];"
            print "    "fmt1" -> "fmt2" [label=\""label"\", fontname=monospace, fontsize=9];"
        }

        function transformation(fmt, prefix, type, label) {
            print ""
	        print "    "fmt" [ label=\""fmt"\" URL=\"@ref MPIX_FMT_"fmt"\"];"
	        print "    "type" [ label=\""type"\" URL=\"@ref "prefix type"\"];"
            print "    "type" -> "fmt" [label=\""label"\", fontname=monospace, fontsize=9];"
        }

        $1 == "MPIX_REGISTER_CONVERT_OP" {
            conversion($4, $5, "")
        }

        $1 == "MPIX_REGISTER_PALETTE_OP" {
            conversion($4, $5, "")
        }

        $1 == "MPIX_REGISTER_QOI_OP" {
            conversion($4, $5, "")
        }

        $1 == "MPIX_REGISTER_DEBAYER_OP" {
            conversion("RGB24", $4, $5"x"$5)
        }

        $1 == "MPIX_REGISTER_CORRECTION_OP" {
            transformation($5, "MPIX_CORRECTION_", $4)
        }

        $1 == "MPIX_REGISTER_KERNEL_3X3_OP" {
            transformation($5, "MPIX_KERNEL_", $4, "3x3")
        }

        $1 == "MPIX_REGISTER_KERNEL_5X5_OP" {
            transformation($5, "MPIX_KERNEL_", $4, "5x5")
        }

        $1 == "MPIX_REGISTER_RESIZE_OP" {
            transformation($5, "MPIX_RESIZE_", $4)
        }

        END {
            print "}"
        }
    ' "$src" >$dst
}

# Scan the sources and generate Graphviz figures out of it
c2dot op_convert
c2dot op_palettize
c2dot op_qoi
c2dot op_debayer
c2dot op_correction
c2dot op_kernel
c2dot op_resize
